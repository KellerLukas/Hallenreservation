template = """
<table width="100%" cellpadding="0" cellspacing="0"
       style="font-family:Arial, Helvetica, sans-serif; font-size:14px; color:#333333;">
  <tr>
    <td>

      <p>Hallo</p>

      <p>
        Es ist eine neue Reservationsbestätigung eingetroffen. Diese betrifft folgende Tage:
      </p>
      
      <ul style="margin:10px 0; padding-left:20px;">
        {dates}
      </ul>

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
