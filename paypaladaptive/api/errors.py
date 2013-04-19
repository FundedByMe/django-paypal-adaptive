class PaypalAdaptiveApiError(RuntimeError):
    pass


class PayError(PaypalAdaptiveApiError):
    pass


class RefundError(PaypalAdaptiveApiError):
    pass


class CancelPreapprovalError(PaypalAdaptiveApiError):
    pass


class PreapproveError(PaypalAdaptiveApiError):
    pass


class IpnError(PaypalAdaptiveApiError):
    pass


class ReceiverError(PaypalAdaptiveApiError):
    pass