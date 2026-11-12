from datetime import datetime, timedelta, timezone


# El contrato de captura usa la hora civil de Lima sin sufijo (UTC-05:00).
LIMA = timezone(timedelta(hours=-5), "America/Lima")


def hora_lima(valor: datetime) -> datetime:
    return valor if valor.tzinfo is None else valor.astimezone(LIMA).replace(tzinfo=None)


def ahora_lima() -> datetime:
    return hora_lima(datetime.now(LIMA))
