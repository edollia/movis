(function(){
  var c=document.getElementById('mx');
  var x=c ? c.getContext('2d') : null;
  var F=14;
  var CHARS='01アイウエオカキクケコ@#$%ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  var MSG='Just Keep Gooning';
  var drops=[], msgCols={}, cols=0, screenW=0, screenH=0, dpr=1;
  var started=false, frozen=false, loopActive=false;
  var raf=0, lastFrame=0, msgTimer=0, idleTimer=0, resizeTimer=0;
  var IDLE_MS=180000;
  var reduceMotion=window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if(document.body.classList.contains('home') && document.getElementById('boot')){
    document.body.classList.add('booting','ui-hidden');
  }

  function boot(){
    var bootEl=document.getElementById('boot');
    if(!bootEl){
      document.body.classList.remove('booting','ui-hidden');
      startMatrix();
      revealUi();
      return;
    }
    var firstLine=bootEl.getAttribute('data-line-one') || 'Knock, knock, Neo.';
    var secondLine=bootEl.getAttribute('data-line-two') || 'Have you gooned today?';
    var lines=[
      {el:document.getElementById('boot-line-1'), text:firstLine},
      {el:document.getElementById('boot-line-2'), text:secondLine, pauseAfter:secondLine.replace(/[?.!]+$/,'')}
    ];
    var lineIndex=0, charIndex=0;

    function finish(){
      lines.forEach(function(line){ if(line.el) line.el.classList.remove('active'); });
      bootEl.classList.add('done');
      document.body.classList.remove('booting');
      setTimeout(function(){
        bootEl.remove();
        startMatrix();
        setTimeout(revealUi, reduceMotion ? 0 : 2000);
      }, reduceMotion ? 120 : 950);
    }

    if(reduceMotion){
      lines.forEach(function(line){
        if(line.el)line.el.textContent=line.text;
      });
      setTimeout(finish, 120);
      return;
    }

    function type(){
      var line=lines[lineIndex];
      if(!line || !line.el){ finish(); return; }
      lines.forEach(function(item){ if(item.el) item.el.classList.remove('active'); });
      line.el.classList.add('active');
      line.el.textContent=line.text.slice(0,charIndex);
      if(charIndex<=line.text.length){
        charIndex++;
        var delay=(54 + Math.random()*42)*1.2;
        if(line.pauseAfter && line.text.slice(0,charIndex-1)===line.pauseAfter)delay=1000;
        setTimeout(type, delay);
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
    var coarse=window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
    if(q && !coarse) q.focus({preventScroll:true});
    armIdleCheck();
  }

  function canvasSize(){
    var rect=c.getBoundingClientRect();
    return {
      width:Math.max(1,Math.round(rect.width || window.innerWidth)),
      height:Math.max(1,Math.round(rect.height || window.innerHeight))
    };
  }

  function init(preserve){
    if(!c || !x)return;
    var oldDrops=drops.slice();
    var oldCols=cols;
    var oldScreenH=screenH || 1;
    var oldMsgCols=msgCols;
    var size=canvasSize();
    dpr=Math.min(2,Math.max(1,window.devicePixelRatio || 1));
    screenW=size.width;
    screenH=size.height;
    c.width=Math.round(screenW*dpr);
    c.height=Math.round(screenH*dpr);
    x.setTransform(dpr,0,0,dpr,0,0);
    cols=Math.max(1,Math.floor(screenW/F));
    drops=Array.from({length:cols},function(_value,i){
      if(preserve && oldCols>0){
        var sourceIndex=Math.round(i*Math.max(0,oldCols-1)/Math.max(1,cols-1));
        var sourceDrop=oldDrops[sourceIndex];
        if(typeof sourceDrop==='number')return Math.round(sourceDrop*(screenH/oldScreenH));
      }
      return Math.floor(Math.random()*-(screenH/F));
    });
    if(preserve && oldCols>0){
      msgCols={};
      Object.keys(oldMsgCols).forEach(function(key){
        var oldIndex=parseInt(key,10);
        if(Number.isNaN(oldIndex))return;
        var nextIndex=Math.round(oldIndex*Math.max(0,cols-1)/Math.max(1,oldCols-1));
        msgCols[nextIndex]=oldMsgCols[key];
      });
    } else {
      msgCols={};
    }
    x.fillStyle='#061606';
    x.fillRect(0,0,screenW,screenH);
  }

  function resizeMatrix(){
    if(!started || frozen || !c || !x)return;
    var size=canvasSize();
    var widthDelta=Math.abs(size.width-screenW);
    var heightDelta=Math.abs(size.height-screenH);
    if(widthDelta<8 && heightDelta<72)return;
    init(true);
  }

  function injectMsg(){
    if(frozen || document.hidden)return;
    var attempts=0, col;
    do { col=Math.floor(Math.random()*cols); attempts++; }
    while(msgCols[col]!==undefined && attempts<20);
    if(msgCols[col]===undefined) msgCols[col]=0;
    scheduleMsg();
  }

  function scheduleMsg(){
    clearTimeout(msgTimer);
    msgTimer=setTimeout(injectMsg, 1500+Math.random()*2500);
  }

  function tubeX(col){
    var base=col*F;
    var nx=(base/screenW-.5)*2;
    return screenW/2+(nx+nx*nx*nx*.035)*screenW/2;
  }

  function tick(){
    if(!x)return;
    x.fillStyle='rgba(0,8,0,0.055)';
    x.fillRect(0,0,screenW,screenH);
    x.font='bold '+F+'px monospace';
    for(var i=0;i<drops.length;i++){
      var r=Math.random();
      var drawX=tubeX(i);
      if(msgCols[i]!==undefined){
        var ci=msgCols[i];
        if(ci<MSG.length){
          x.fillStyle = r>.97 ? '#fff' : r>.9 ? '#afffaf' : '#00cc00';
          x.fillText(MSG[ci], drawX, drops[i]*F);
          msgCols[i]++;
        } else {
          delete msgCols[i];
          x.fillStyle = r>.97 ? '#fff' : r>.9 ? '#afffaf' : '#00cc00';
          x.fillText(CHARS[Math.floor(Math.random()*CHARS.length)], drawX, drops[i]*F);
        }
      } else {
        x.fillStyle = r>.97 ? '#fff' : r>.9 ? '#afffaf' : '#00cc00';
        x.fillText(CHARS[Math.floor(Math.random()*CHARS.length)], drawX, drops[i]*F);
      }
      if(drops[i]*F>screenH && Math.random()>.975) drops[i]=0;
      drops[i]++;
    }
  }

  function loop(now){
    if(!started || frozen){
      loopActive=false;
      raf=0;
      return;
    }
    raf=requestAnimationFrame(loop);
    if(document.hidden)return;
    if(!lastFrame)lastFrame=now;
    if(now-lastFrame<60)return;
    lastFrame=now;
    tick();
  }

  function startLoop(){
    if(loopActive)return;
    loopActive=true;
    lastFrame=0;
    raf=requestAnimationFrame(loop);
  }

  function stopLoop(){
    loopActive=false;
    if(raf)cancelAnimationFrame(raf);
    raf=0;
  }

  function startMatrix(){
    if(started || !c || !x)return;
    started=true;
    document.body.classList.add('rain-arming');
    init();
    if(reduceMotion){
      tick();
      document.body.classList.remove('rain-arming');
      document.body.classList.add('rain-live');
      return;
    }
    injectMsg();
    startLoop();
    setTimeout(function(){
      document.body.classList.remove('rain-arming');
      document.body.classList.add('rain-live');
    },620);
  }

  function freezeMatrix(){
    frozen=true;
    document.body.classList.add('standby');
    clearTimeout(msgTimer);
    stopLoop();
  }

  function reloadPage(){
    window.location.reload();
  }

  function showIdlePrompt(){
    if(frozen || !document.body.classList.contains('home'))return;
    freezeMatrix();
    var overlay=document.createElement('div');
    overlay.className='idle-check';
    overlay.setAttribute('role','dialog');
    overlay.setAttribute('aria-modal','true');
    overlay.setAttribute('aria-label','Are you ok?');
    overlay.innerHTML=[
      '<div class="idle-monitor">',
      '<button class="idle-x" type="button" aria-label="Reload">x</button>',
      '<p class="idle-line">are you ok?</p>',
      '<p class="idle-line">do you need help?</p>',
      '<button class="idle-resume" type="button">reload</button>',
      '</div>'
    ].join('');
    document.body.appendChild(overlay);
    overlay.addEventListener('click',function(e){
      if(e.target===overlay || e.target.closest('button'))reloadPage();
    });
    function handleIdleKey(e){
      if(!['Escape','Enter',' ','r','R'].includes(e.key))return;
      e.preventDefault();
      window.removeEventListener('keydown',handleIdleKey);
      reloadPage();
    }
    window.addEventListener('keydown',handleIdleKey);
    var resume=overlay.querySelector('.idle-resume');
    if(resume)resume.focus({preventScroll:true});
  }

  function armIdleCheck(){
    if(!document.body.classList.contains('home'))return;
    clearTimeout(idleTimer);
    idleTimer=setTimeout(showIdlePrompt, IDLE_MS);
  }

  ['pointerdown','keydown','touchstart','mousemove'].forEach(function(eventName){
    window.addEventListener(eventName,function(){
      if(!frozen && !document.body.classList.contains('booting'))armIdleCheck();
    },{passive:true});
  });

  document.addEventListener('visibilitychange',function(){
    if(!started || frozen)return;
    if(document.hidden){
      clearTimeout(msgTimer);
      stopLoop();
      return;
    }
    injectMsg();
    startLoop();
    armIdleCheck();
  });

  window.addEventListener('resize',function(){
    clearTimeout(resizeTimer);
    resizeTimer=setTimeout(resizeMatrix,180);
  });
  boot();
})();
