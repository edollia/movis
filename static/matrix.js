(function(){
  var c=document.getElementById('mx');
  var x=c ? c.getContext('2d') : null;
  var F=14;
  var CHARS='01アイウエオカキクケコ@#$%ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  var MSG='Just Keep Gooning';
  var drops=[], msgCols={}, cols=0, started=false;

  function boot(){
    var bootEl=document.getElementById('boot');
    if(!bootEl){ startMatrix(); revealUi(); return; }
    var lines=[
      {el:document.getElementById('boot-line-1'), text:'Knock, knock, Neo.'},
      {el:document.getElementById('boot-line-2'), text:'Have you gooned today.'}
    ];
    var lineIndex=0, charIndex=0;

    function finish(){
      lines.forEach(function(line){ if(line.el) line.el.classList.remove('active'); });
      bootEl.classList.add('done');
      document.body.classList.remove('booting');
      setTimeout(function(){
        bootEl.remove();
        startMatrix();
        setTimeout(revealUi, 2000);
      }, 950);
    }

    function type(){
      var line=lines[lineIndex];
      if(!line || !line.el){ finish(); return; }
      lines.forEach(function(item){ if(item.el) item.el.classList.remove('active'); });
      line.el.classList.add('active');
      line.el.textContent=line.text.slice(0,charIndex);
      if(charIndex<=line.text.length){
        charIndex++;
        setTimeout(type, 54 + Math.random()*42);
        return;
      }
      line.el.classList.remove('active');
      lineIndex++;
      charIndex=0;
      if(lineIndex<lines.length){
        setTimeout(type, 520);
      } else {
        setTimeout(finish, 820);
      }
    }

    setTimeout(type, 520);
  }

  function revealUi(){
    document.body.classList.remove('ui-hidden');
    var q=document.querySelector('.home-search input[name="q"]');
    if(q) q.focus({preventScroll:true});
  }

  function init(){
    if(!c || !x)return;
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
    if(!x)return;
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

  function startMatrix(){
    if(started || !c || !x)return;
    started=true;
    document.body.classList.add('rain-live');
    init();
    injectMsg();
    setInterval(tick,60);
  }

  var rt;
  window.addEventListener('resize',function(){ clearTimeout(rt); rt=setTimeout(init,200); });
  boot();
})();
