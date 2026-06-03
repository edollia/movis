(function(){
  var c=document.getElementById('mx'); if(!c)return;
  var x=c.getContext('2d');
  var F=14;
  var CHARS='01アイウエオカキクケコ@#$%ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  var MSG='Just Keep Gooning';
  var drops=[], msgCols={}, cols=0;

  function init(){
    c.width=window.innerWidth; c.height=window.innerHeight;
    cols=Math.floor(c.width/F);
    drops=Array.from({length:cols},function(){
      return Math.floor(Math.random()*-(c.height/F));
    });
    msgCols={};
    x.fillStyle='#000'; x.fillRect(0,0,c.width,c.height);
  }

  function injectMsg(){
    var attempts=0, col;
    do { col=Math.floor(Math.random()*cols); attempts++; }
    while(msgCols[col]!==undefined && attempts<20);
    if(msgCols[col]===undefined) msgCols[col]=0;
    setTimeout(injectMsg, 1500+Math.random()*2500);
  }

  function tick(){
    x.fillStyle='rgba(0,0,0,0.05)'; x.fillRect(0,0,c.width,c.height);
    x.font='bold '+F+'px monospace';
    for(var i=0;i<drops.length;i++){
      var r=Math.random();
      if(msgCols[i]!==undefined){
        var ci=msgCols[i];
        if(ci<MSG.length){
          x.fillStyle = r>.97 ? '#fff' : r>.9 ? '#afffaf' : '#00cc00';
          x.fillText(MSG[ci], i*F, drops[i]*F);
          msgCols[i]++;
        } else {
          delete msgCols[i];
          x.fillStyle = r>.97 ? '#fff' : r>.9 ? '#afffaf' : '#00cc00';
          x.fillText(CHARS[Math.floor(Math.random()*CHARS.length)], i*F, drops[i]*F);
        }
      } else {
        x.fillStyle = r>.97 ? '#fff' : r>.9 ? '#afffaf' : '#00cc00';
        x.fillText(CHARS[Math.floor(Math.random()*CHARS.length)], i*F, drops[i]*F);
      }
      if(drops[i]*F>c.height && Math.random()>.975) drops[i]=0;
      drops[i]++;
    }
  }

  var rt;
  window.addEventListener('resize',function(){ clearTimeout(rt); rt=setTimeout(init,200); });
  init();
  injectMsg();
  setInterval(tick,60);
})();
