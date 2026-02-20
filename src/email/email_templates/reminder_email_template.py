template = """
<table width="100%" cellpadding="0" cellspacing="0"
       style="font-family:Arial, Helvetica, sans-serif; font-size:14px; color:#333333;">
  <tr>
    <td>

      <p>Hallo</p>

      <p>
        In <strong>{days}</strong> Tagen am <strong>{date}</strong> liegen folgende Reservationen vor:
      </p>

      <ul style="margin:10px 0; padding-left:20px;">
        {reservations}
      </ul>

      <p>
        Du erhältst diese Nachricht, weil du den Hallenreservation-Reminder aktiviert hast.
        Du kannst den Reminder hier anpassen oder abbestellen:
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

reservation_list_template = """
  <li style="padding:4px 0; font-size:14px;">
    {filename}
  </li>
"""
