"""Single-worker shared execution slot; independent of model-supplied state."""


class ExecutionBusy(Exception):
    pass


class ExecutionSlot:
    def __init__(self):
        self.owner: str | None = None

    def claim(self, owner: str):
        if self.owner is not None:
            raise ExecutionBusy('Another investigation or agent workflow is already running.')
        self.owner = owner

    def release(self, owner: str):
        if self.owner == owner:
            self.owner = None
