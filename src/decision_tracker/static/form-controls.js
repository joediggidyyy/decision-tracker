// Disabled sections are inapplicable; collapsed details remain applicable.
export const activeControl=(n,owner)=>!!n&&n.isConnected&&owner.contains(n)&&!n.matches(':disabled')&&!n.closest('[hidden]');
