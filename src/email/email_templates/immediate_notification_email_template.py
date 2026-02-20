template = """
<table width="100%" cellpadding="0" cellspacing="0"
       style="font-family:Arial, Helvetica, sans-serif; font-size:14px; color:#333333;">
  <tr>
    <td>

      <p>Hallo</p>

      <p>
        Es gibt eine neue Reservation für den <strong>{date}</strong>:
      </p>
      <p>
        {filename}
      </p>

      <p>
        Du erhältst diese Nachricht, weil du den Halleninfo-Service aktiviert hast.
        Du kannst deine Benachrichtigungseinstellungen hier anpassen oder den Service abbestellen:
        <br>
        {subscription_manage_url}
      </p>

      <p>
        Bei Fragen kannst du dich hier melden:
        {support_email_address}
      </p>

      <p>
        Gruss<br>
        TV Würenlos
      </p>

    </td>
  </tr>
</table>
"""
