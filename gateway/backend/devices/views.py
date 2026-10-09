"""REST API for devices, sites, memberships and pairing."""

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Device, Membership, Site
from .permissions import DeviceAccessPermission
from .serializers import (
    DeviceSerializer,
    MembershipSerializer,
    MembershipWriteSerializer,
    PairingClaimCreateSerializer,
    PairingRedeemSerializer,
    SiteSerializer,
)
from .services import (
    PairingError,
    create_pairing_claim,
    redeem_pairing_code,
    register_failed_attempt,
)


class SiteViewSet(viewsets.ModelViewSet):
    serializer_class = SiteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Site.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class DeviceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Devices are never created through the API: pairing does that."""

    serializer_class = DeviceSerializer
    permission_classes = [IsAuthenticated, DeviceAccessPermission]

    def get_queryset(self):
        queryset = (
            Device.objects.for_user(self.request.user)
            .select_related("site")
            .prefetch_related("capabilities", "memberships__user")
        )
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def _require_owner(self, device):
        if device.role_of(self.request.user) != Membership.Role.OWNER:
            raise PermissionDenied("Seul le propriétaire peut effectuer cette action.")

    @action(detail=True, methods=["get", "post"])
    def members(self, request, pk=None):
        device = self.get_object()
        if request.method == "GET":
            return Response(
                MembershipSerializer(device.memberships.all(), many=True).data
            )

        self._require_owner(device)
        payload = MembershipWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        user = payload.validated_data["username"]
        if device.memberships.filter(user=user).exists():
            raise ValidationError("Cet utilisateur est déjà membre.")
        membership = device.add_member(user, role=payload.validated_data["role"])
        membership.invited_by = request.user
        membership.save(update_fields=["invited_by"])
        return Response(
            MembershipSerializer(membership).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["delete"], url_path=r"members/(?P<user_id>[0-9]+)")
    def remove_member(self, request, pk=None, user_id=None):
        device = self.get_object()
        self._require_owner(device)
        membership = device.memberships.filter(user_id=user_id).first()
        if membership is None:
            return Response(
                {"detail": "Membre introuvable."}, status=status.HTTP_404_NOT_FOUND
            )
        if membership.role == Membership.Role.OWNER:
            raise ValidationError(
                "Le propriétaire ne peut pas être retiré : transférez le Bourgeon."
            )
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def transfer(self, request, pk=None):
        device = self.get_object()
        self._require_owner(device)
        payload = MembershipWriteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        device.transfer_to(payload.validated_data["username"])
        return Response(DeviceSerializer(device, context={"request": request}).data)


class PairingClaimCreateView(APIView):
    """Register a freshly flashed device (called by the provisioning tool)."""

    permission_classes = [IsAdminUser]

    def post(self, request):
        payload = PairingClaimCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        device = Device.objects.create(
            device_id=data["device_id"],
            slug=data["device_id"],
            name=data.get("name") or data["device_id"],
            model=data.get("model", ""),
            status=Device.Status.PENDING,
        )
        claim, code = create_pairing_claim(
            device,
            code=data.get("code") or None,
            ttl_hours=data.get("ttl_hours"),
            bootstrap_fingerprint=data.get("bootstrap_fingerprint", ""),
        )
        return Response(
            {
                "device_id": device.device_id,
                "code": code,
                "expires_at": claim.expires_at,
            },
            status=status.HTTP_201_CREATED,
        )


class PairingRedeemView(APIView):
    """Attach a device to the calling user with the code shown on its screen."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = PairingRedeemSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        code = payload.validated_data["code"]
        try:
            device = redeem_pairing_code(request.user, code)
        except PairingError as exc:
            register_failed_attempt(code)
            return Response(
                {"detail": str(exc), "code": exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = DeviceSerializer(device, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
