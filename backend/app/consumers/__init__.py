"""The stream consumers, one module per seam that inverts a cross-domain write.

`votes` lets `catalog` own its own `parts` write, and `price_alerts` lets
`admin` own the alert rows and the SES send. These import no router.
"""
