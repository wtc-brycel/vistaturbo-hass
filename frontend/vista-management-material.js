window.VISTA_MANAGEMENT_STYLES = String(window.VISTA_MANAGEMENT_STYLES || "") + String.raw`
:host{
  --vt-surface-header:color-mix(in srgb,var(--vt-card) 90%,var(--vt-text));
  --vt-subtle-surface:color-mix(in srgb,var(--vt-card) 96%,var(--vt-text));
  --vt-card-border:var(--ha-card-border-color,var(--divider-color,#e0e0e0));
  --vt-card-border-width:var(--ha-card-border-width,1px);
  --vt-card-shadow:var(--ha-card-box-shadow,none);
  --vt-inner-divider:color-mix(in srgb,var(--vt-divider) 72%,transparent);
  --vt-elevation-dialog:var(--dialog-box-shadow,0 8px 28px rgba(0,0,0,.28));
}
.surface{border:var(--vt-card-border-width) solid var(--vt-card-border);box-shadow:var(--vt-card-shadow)}
:host .rail-head,:host .management-bar{background:var(--vt-surface-header)}
.surface-head{min-height:52px;background:var(--vt-surface-header);border-bottom:1px solid var(--vt-inner-divider)}
.surface-head h2,.detail-head h2{font-weight:500;letter-spacing:0}
.surface-head .count{font-variant-numeric:tabular-nums}
.ha-button{min-height:40px;border-radius:20px;padding-inline:16px;font-weight:500;letter-spacing:.01em}
.ha-button.filled{box-shadow:none}
.search-box{height:44px;border-radius:8px}
.surface .data-table th{background:var(--vt-surface-header)}
.surface .data-table th,.surface .data-table td{border-bottom-color:var(--vt-inner-divider)}
.detail-head,.surface .partition-detail-head{background:var(--vt-subtle-surface);border-bottom-color:var(--vt-inner-divider)}
.surface .detail-tabs,.surface .record-tabs{background:var(--vt-subtle-surface);border-bottom-color:var(--vt-inner-divider)}
.input,.select{min-height:52px;border-radius:8px 8px 0 0}
.filter-chip{height:32px}
.users-toolbar{padding-bottom:6px}
.filter-row{padding-bottom:10px;border-bottom:1px solid var(--vt-inner-divider)}
.user-list{border-top:0}
.user-row{position:relative;min-height:62px;border-bottom-color:var(--vt-inner-divider)}
.user-row.selected::before{content:"";position:absolute;inset-block:9px;inset-inline-start:0;width:3px;border-radius:0 3px 3px 0;background:var(--vt-primary)}
.user-row.selected .user-number{color:var(--vt-primary)}
.mini-pill,.origin-pill{border-radius:999px;padding-inline:7px}
.detail-actions{background:var(--vt-subtle-surface);border-top-color:var(--vt-inner-divider)}
.authority-table th{background:var(--vt-subtle-surface);border-bottom-color:var(--vt-inner-divider)}
.authority-table td{border-bottom-color:var(--vt-inner-divider)}
.surface .partition-select{position:relative;border-bottom-color:var(--vt-inner-divider)}
.surface .partition-select.selected::before{content:"";position:absolute;inset-block:9px;inset-inline-start:0;width:3px;border-radius:0 3px 3px 0;background:var(--vt-primary)}
.surface .partition-select.selected .partition-select-number{color:var(--vt-primary)}
.partition-edit{border-color:var(--vt-inner-divider)}
.switch-row input[type="checkbox"]{appearance:none;-webkit-appearance:none;width:40px;height:22px;margin:0;border:0;border-radius:11px;background:color-mix(in srgb,var(--vt-secondary) 48%,transparent);position:relative;cursor:pointer;flex:0 0 auto;transition:background .12s ease}
.switch-row input[type="checkbox"]::before{content:"";position:absolute;width:18px;height:18px;inset-block-start:2px;inset-inline-start:2px;border-radius:50%;background:var(--vt-card);box-shadow:0 1px 2px rgba(0,0,0,.28);transition:transform .12s ease}
.switch-row input[type="checkbox"]:checked{background:var(--vt-primary)}
.switch-row input[type="checkbox"]:checked::before{transform:translateX(18px);background:#fff}
.switch-row input[type="checkbox"]:focus-visible,.partition-edit-head input[type="checkbox"]:focus-visible{outline:2px solid var(--vt-primary);outline-offset:3px}
.partition-edit-head input[type="checkbox"]{appearance:none;-webkit-appearance:none;width:20px;height:20px;margin:0;border:2px solid var(--vt-secondary);border-radius:2px;background:transparent;display:grid;place-items:center;cursor:pointer}
.partition-edit-head input[type="checkbox"]:checked{border-color:var(--vt-primary);background:var(--vt-primary)}
.partition-edit-head input[type="checkbox"]:checked::after{content:"";width:9px;height:5px;border-left:2px solid #fff;border-bottom:2px solid #fff;transform:translateY(-1px) rotate(-45deg)}
.partition-edit-head input[type="checkbox"]:disabled{opacity:.55;cursor:default}
dialog{width:min(var(--ha-dialog-width-md,580px),calc(100vw - 32px));border-radius:var(--ha-dialog-border-radius,28px);box-shadow:var(--vt-elevation-dialog)}
dialog::backdrop{background:rgba(0,0,0,.4)}
.dialog-head{min-height:64px;padding:8px 8px 4px 20px;border-bottom:0}
.dialog-head h3{font-size:20px;font-weight:500;line-height:1.25}
dialog:not(.admin-dialog) .dialog-head .icon-button{position:relative;font-size:0}
dialog:not(.admin-dialog) .dialog-head .icon-button::before,dialog:not(.admin-dialog) .dialog-head .icon-button::after{content:"";position:absolute;width:18px;height:2px;border-radius:1px;background:currentColor}
dialog:not(.admin-dialog) .dialog-head .icon-button::before{transform:rotate(45deg)}
dialog:not(.admin-dialog) .dialog-head .icon-button::after{transform:rotate(-45deg)}
.dialog-scroll{padding:16px 24px 8px}
.dialog-actions{padding:12px 16px 16px;border-top:0}
@media(max-width:600px){
  dialog{width:100vw;max-width:100vw;border-radius:24px 24px 0 0}
  .surface{border-radius:var(--ha-card-border-radius,12px)}
}
`;
