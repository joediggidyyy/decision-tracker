// Long-lived page/dialog nodes share measured focus clearance, without scroll polling.
export function measureHeader(header,scrollport,property){
 const observer=new ResizeObserver(()=>scrollport.style.setProperty(property,header.getBoundingClientRect().height+'px'));
 observer.observe(header);
 return ()=>observer.disconnect();
}

export function installLibraryHeader(page,stage){
 const heading=page.querySelector('.admin-heading'),toggle=page.querySelector('#saved-view-toggle');
 const band=document.createElement('div'),context=document.createElement('div');
 context.className='library-heading-context';
 const slots=[heading,toggle].map(node=>{const slot=document.createComment('header home');node.before(slot);return {node,slot};});
 const media=matchMedia('(min-width:981px)');
 const update=()=>{
  const wide=media.matches&&page.clientWidth>960;
  if(wide&&!band.isConnected){slots[0].slot.after(band);band.append(heading,context);context.append(toggle);band.className='library-header-locked';}
  else if(!wide&&band.isConnected){for(const {node,slot} of slots)slot.after(node);band.remove();}
  band.classList.toggle('header-overflow',wide&&band.scrollHeight>innerHeight*.45);
  const height=wide?band.getBoundingClientRect().height:0;
  page.style.setProperty('--library-heading-height',height+'px');
  page.parentElement.style.setProperty('--library-heading-height',height+'px');
 };
 const observer=new ResizeObserver(update);observer.observe(page);observer.observe(band);
 media.addEventListener('change',update);update();
 return ()=>{observer.disconnect();media.removeEventListener('change',update);};
}
