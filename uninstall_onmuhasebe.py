# Odoo shell'de çalıştırılacak: modül kaldırma (env zaten tanımlı)
mod = env['ir.module.module'].search([('name', '=', 'mobilsoft_onmuhasebe')], limit=1)
if mod and mod.state == 'installed':
    mod.button_immediate_uninstall()
    env.cr.commit()
    print('OK: mobilsoft_onmuhasebe kaldırıldı.')
elif mod:
    print('SKIP: Modül zaten kurulu değil (state=%s).' % mod.state)
else:
    print('SKIP: mobilsoft_onmuhasebe kaydı bulunamadı.')
