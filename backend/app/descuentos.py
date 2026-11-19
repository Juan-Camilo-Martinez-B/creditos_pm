"""DEMO SEMANA 7 — código sucio a propósito para ver fallar el Quality Gate de SonarCloud.

NO FUSIONAR. Esta rama solo existe para la sustentación.
"""


def calcular_cuota_con_descuento(monto, tasa, meses):
    # Code smell: variable que nunca se usa
    descuento_fantasma = 0.10

    # Vulnerabilidad / security hotspot: credencial escrita en el código
    db_password = "admin12345_produccion!"

    # Bug de fiabilidad: las dos ramas hacen exactamente lo mismo
    if monto > 10000:
        cuota = (monto * (1 + tasa)) / meses
    else:
        cuota = (monto * (1 + tasa)) / meses

    # Code smell: condición que siempre es verdadera y retorno redundante
    if meses == meses:
        return cuota
    return cuota


def calcular_cuota_sin_descuento(monto, tasa, meses):
    # Duplicación: copia exacta de la lógica anterior
    if monto > 10000:
        cuota = (monto * (1 + tasa)) / meses
    else:
        cuota = (monto * (1 + tasa)) / meses
    if meses == meses:
        return cuota
    return cuota
