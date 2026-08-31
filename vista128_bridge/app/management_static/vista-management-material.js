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
.user-row{position:relative;border-bottom-color:var(--vt-inner-divider)}
.user-row.selected::before{content:"";position:absolute;inset-block:9px;inset-inline-start:0;width:3px;border-radius:0 3px 3px 0;background:var(--vt-primary)}
.user-row.selected .user-number{color:var(--vt-primary)}
.surface .partition-select{position:relative;border-bottom-color:var(--vt-inner-divider)}
.surface .partition-select.selected::before{content:"";position:absolute;inset-block:9px;inset-inline-start:0;width:3px;border-radius:0 3px 3px 0;background:var(--vt-primary)}
.surface .partition-select.selected .partition-select-number{color:var(--vt-primary)}
.partition-edit{border-color:var(--vt-inner-divider)}
dialog{width:min(var(--ha-dialog-width-md,580px),calc(100vw - 32px));border-radius:var(--ha-dialog-border-radius,28px);box-shadow:var(--vt-elevation-dialog)}
dialog::backdrop{background:rgba(0,0,0,.4)}
.dialog-head{min-height:64px;padding:8px 8px 4px 20px;border-bottom:0}
.dialog-head h3{font-size:20px;font-weight:500;line-height:1.25}
.dialog-scroll{padding:16px 24px 8px}
.dialog-actions{padding:12px 16px 16px;border-top:0}
@media(max-width:600px){
  dialog{width:100vw;max-width:100vw;border-radius:24px 24px 0 0}
  .surface{border-radius:var(--ha-card-border-radius,12px)}
}
`;
