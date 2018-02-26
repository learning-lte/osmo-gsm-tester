#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

hlr = suite.hlr()
bts = suite.bts()
pcu = bts.pcu()
mgw_msc = suite.mgw()
mgw_bsc = suite.mgw()
stp = suite.stp()
ggsn = suite.ggsn()
sgsn = suite.sgsn(hlr, ggsn)
msc = suite.msc(hlr, mgw_msc, stp)
bsc = suite.bsc(msc, mgw_bsc, stp)
ms = suite.modem()

bsc.bts_add(bts)
sgsn.bts_add(bts)

print('start network...')
hlr.start()
stp.start()
ggsn.start()
sgsn.start()
msc.start()
mgw_msc.start()
mgw_bsc.start()
bsc.start()

bts.start()
wait(bsc.bts_is_connected, bts)
print('Waiting for bts to be ready...')
wait(bts.ready_for_pcu)
pcu.start()

hlr.subscriber_add(ms)

ms.connect(msc.mcc_mnc())
ms.attach()

ms.log_info()

print('waiting for modems to attach...')
wait(ms.is_connected, msc.mcc_mnc())
wait(msc.subscriber_attached, ms)

print('waiting for modems to attach to data services...')
wait(ms.is_attached)

# We need to use inet46 since ofono qmi only uses ipv4v6 eua (OS#2713)
ctx_id_v4 = ms.activate_context(apn='inet46', protocol=ms.CTX_PROT_IPv4)
sleep(5)
# TODO: send ping to server or open TCP conn with a socket in python
ms.deactivate_context(ctx_id_v4)

# We need to use inet46 since ofono qmi only uses ipv4v6 eua (OS#2713)
ctx_id_v6 = ms.activate_context(apn='inet46', protocol=ms.CTX_PROT_IPv6)
sleep(5)
# TODO: send ping to server or open TCP conn with a socket in python
ms.deactivate_context(ctx_id_v6)

# IPv46 (dual) not supported in ofono qmi: org.ofono.Error.Failed: Operation failed (36)
# ctx_id_v46 = ms.activate_context(apn='inet46', protocol=ms.CTX_PROT_IPv46)
# sleep(5)
# TODO: send ping to server or open TCP conn with a socket in python
# ms.deactivate_context(ctx_id_v46)
