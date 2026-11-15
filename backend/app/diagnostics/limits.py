"""Give the broker time to return its bounded result before the caller times out."""

BROKER_REQUEST_SECONDS = 7
CLIENT_READ_SECONDS = BROKER_REQUEST_SECONDS + 1
CLIENT_REQUEST_SECONDS = CLIENT_READ_SECONDS + 1
