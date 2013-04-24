from errors import ReceiverError


class Receiver():
    email = None
    amount = None
    primary = False

    def __init__(self, email=None, amount=None, primary=False):
        self.email = email
        self.amount = amount
        self.primary = primary

    def to_dict(self):
        return {'email': self.email,
                'amount': self.amount,
                'primary': self.primary}

    def __unicode__(self):
        return self.email


class ReceiverList():
    receivers = None

    def __init__(self, receivers=None):
        self.receivers = []
        if receivers is not None:
            for receiver in receivers:
                self.append(receiver)

    def append(self, receiver):
        if not isinstance(receiver, Receiver):
            raise ReceiverError("receiver needs to be instance of Receiver")
        self.receivers.append(receiver)

    def to_dict(self):
        self.has_primary()
        return [r.to_dict() for r in self.receivers]

    def __len__(self):
        return len(self.receivers)

    def has_primary(self):
        n_primary = len(filter(lambda r: r.primary is True, self.receivers))

        if n_primary > 1:
            raise ReceiverError("There can only be one primary Receiver")

        return n_primary == 1

    @property
    def total_amount(self):
        return sum([r.amount for r in self.receivers])