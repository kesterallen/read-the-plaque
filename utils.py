
from google.appengine.api import mail
import logging

ADMIN_EMAIL = 'kester+readtheplaque@gmail.com'
NOTIFICATION_SENDER_EMAIL = 'kester@gmail.com'

class SubmitError(Exception):
    pass

def latlng_angles_to_dec(ref, latlng_angles):
    """Convert a degrees, hours, minutes tuple to decimal degrees."""
    latlng = float(latlng_angles[0]) + \
             float(latlng_angles[1]) / 60.0 + \
             float(latlng_angles[2]) / 3600.0
    if ref == 'N' or ref == 'E':
        pass
    elif ref == 'S' or ref == 'W':
        latlng *= -1.0
    else:
        raise SubmitError(
            'reference "%s" needs to be either N, S, E, or W' % ref)

    logging.info("converted %s %s %s to %s" % (
        latlng_angles[0], latlng_angles[1], latlng_angles[2], latlng))
    return latlng

def email_admin(msg, body):
    try:
        mail.send_mail(sender=NOTIFICATION_SENDER_EMAIL,
                       to=ADMIN_EMAIL,
                       subject=msg,
                       body=body,
                       html=body)
    except Exception as err:
        logging.debug('mail failed: %s, %s' % (msg, err))

