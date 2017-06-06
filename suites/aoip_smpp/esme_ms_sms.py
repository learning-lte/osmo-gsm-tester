#!/usr/bin/env python3

# This test checks following use-cases:
# * SMPP interface of SMSC accepts SMPP clients (ESMEs) with password previously
#   defined in its configuration file.
# * ESME can send an SMS to an already registered MS when SMSC is in 'forward' mode.

from osmo_gsm_tester.test import *

SMPP_ESME_RINVDSTADR = 0x0000000B

hlr = suite.hlr()
bts = suite.bts()
mgcpgw = suite.mgcpgw(bts_ip=bts.remote_addr())
msc = suite.msc(hlr, mgcpgw)
bsc = suite.bsc(msc)
stp = suite.stp()
bsc.bts_add(bts)

ms = suite.modem()
esme = suite.esme()
msc.smsc.esme_add(esme)

hlr.start()
stp.start()
msc.start()
mgcpgw.start()
bsc.start()
bts.start()

esme.connect()
hlr.subscriber_add(ms)
ms.connect(msc.mcc_mnc())

ms.log_info()
print('waiting for modem to attach...')
wait(ms.is_connected, msc.mcc_mnc())
wait(msc.subscriber_attached, ms)

print('sending first sms...')
msg = Sms(esme.msisdn, ms.msisdn, 'smpp send message')
esme.sms_send(msg)
wait(ms.sms_was_received, msg)

print('sending second sms (unicode chars not in gsm aplhabet)...')
msg = Sms(esme.msisdn, ms.msisdn, 'chars:[кизаçйж]')
esme.sms_send(msg)
wait(ms.sms_was_received, msg)

# FIXME: This test is not failing with error but succeeds, need to check why: (forward vs store policy?)
# wrong_msisdn = ms.msisdn + esme.msisdn
# print('sending third sms (with wrong msisdn %s)' % wrong_msisdn)
# msg = Sms(esme.msisdn, wrong_msisdn, 'smpp message with wrong dest')
# esme.run_method_expect_failure(SMPP_ESME_RINVDSTADR, esme.sms_send, msg)

esme.disconnect()