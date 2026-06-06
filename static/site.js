(function(){
  var ONLINE_MS=2000;
  var SUPPORT_MS=10000;

  function setSignalMode(mode){
    document.querySelectorAll('[data-signal]').forEach(function(signal){
      signal.classList.toggle('show-support', mode==='support');
    });
  }

  function cycleSignal(){
    setSignalMode('online');
    setTimeout(function(){
      setSignalMode('support');
      setTimeout(cycleSignal, SUPPORT_MS);
    }, ONLINE_MS);
  }

  function bindTapSounds(){
    document.querySelectorAll('[data-tap-sound]').forEach(function(el){
      el.addEventListener('click',function(event){
        if(el.tagName==='A' && el.target==='_blank'){
          event.preventDefault();
          var opened=window.open(el.href,'_blank','noopener,noreferrer');
          if(opened)opened.opener=null;
        }
        var src=el.getAttribute('data-tap-sound');
        if(!src)return;
        try{
          var audio=new Audio(src);
          audio.volume=.55;
          audio.play().catch(function(){});
        }catch(e){}
      });
    });
  }

  function toggleControls(root, enabled){
    if(!root)return;
    root.querySelectorAll('a,button,input,select,textarea').forEach(function(el){
      if(enabled){
        el.removeAttribute('tabindex');
      } else {
        el.setAttribute('tabindex','-1');
      }
    });
  }

  function syncCardControls(card){
    var active=card.classList.contains('is-active');
    var flipped=card.classList.contains('is-flipped');
    var front=card.querySelector('.movie-front');
    var back=card.querySelector('.movie-back');
    if(front)front.setAttribute('aria-hidden',active && flipped ? 'true' : 'false');
    if(back)back.setAttribute('aria-hidden',active && flipped ? 'false' : 'true');
    toggleControls(front,active && !flipped);
    toggleControls(back,active && flipped);
  }

  function setCardFlipped(card, flipped){
    card.classList.toggle('is-flipped',flipped);
    card.querySelectorAll('[data-flip]').forEach(function(btn){
      btn.setAttribute('aria-pressed',flipped ? 'true' : 'false');
    });
    syncCardControls(card);
  }

  function clamp(value,min,max){
    return Math.max(min,Math.min(value,max));
  }

  function px(value){
    return Math.round(value*10)/10+'px';
  }

  function initCarousels(){
    document.querySelectorAll('[data-carousel]').forEach(function(carousel){
      var track=carousel.querySelector('[data-carousel-track]');
      var slides=Array.prototype.slice.call(carousel.querySelectorAll('[data-slide]'));
      var prev=carousel.querySelector('[data-carousel-prev]');
      var next=carousel.querySelector('[data-carousel-next]');
      var count=carousel.querySelector('[data-carousel-count]');
      var activeIndex=0;
      var dragStartX=0;
      var dragStartY=0;
      var dragging=false;
      var dragMoved=false;
      var resizeTimer=0;

      if(!track || !slides.length)return;

      function deckMetrics(){
        var stage=carousel.querySelector('[data-deck-stage]') || track;
        var stageWidth=stage.clientWidth || track.clientWidth || window.innerWidth;
        var card=slides[0].querySelector('[data-flip-card]');
        var cardWidth=card ? card.getBoundingClientRect().width : 360;
        var isMobile=window.matchMedia && window.matchMedia('(max-width: 760px)').matches;
        var spread=isMobile ? .34 : .48;
        var divisor=isMobile ? 3.4 : 2.55;
        var side=Math.min(cardWidth*spread,Math.max(isMobile ? 54 : 78,(stageWidth-cardWidth)/divisor));
        return {side:side};
      }

      function applySlidePosition(slide,delta,metrics){
        var abs=Math.abs(delta);
        var sign=delta<0 ? -1 : 1;
        var offsetMap=[0,1,1.58,2.04,2.48];
        var scaleMap=[1,.88,.78,.69,.64];
        var opacityMap=[1,.72,.42,.18,0];
        var blurMap=[0,.45,1.7,3.4,6];
        var yMap=[0,10,21,32,42];
        var rotateMap=[0,7,11,14,16];
        var capped=Math.min(abs,4);

        slide.style.setProperty('--deck-x',px(sign*metrics.side*offsetMap[capped]));
        slide.style.setProperty('--deck-y',px(yMap[capped]));
        slide.style.setProperty('--deck-r',(sign*-rotateMap[capped])+'deg');
        slide.style.setProperty('--deck-s',scaleMap[capped]);
        slide.style.setProperty('--deck-o',opacityMap[capped]);
        slide.style.setProperty('--deck-blur',px(blurMap[capped]));
        slide.style.setProperty('--deck-depth',px(-70*capped));
        slide.style.setProperty('--deck-z',String(80-capped));
        slide.classList.toggle('is-visible',abs<=3);
        slide.classList.toggle('is-far',abs>3);
      }

      function setActive(index,focusTrack){
        activeIndex=clamp(index,0,slides.length-1);
        var metrics=deckMetrics();
        slides.forEach(function(slide,i){
          var card=slide.querySelector('[data-flip-card]');
          var isActive=i===activeIndex;
          var delta=i-activeIndex;
          slide.classList.toggle('is-active-slide',isActive);
          slide.setAttribute('aria-hidden',isActive ? 'false' : 'true');
          applySlidePosition(slide,delta,metrics);
          if(card){
            card.classList.toggle('is-active',isActive);
            if(!isActive)setCardFlipped(card,false);
            syncCardControls(card);
          }
        });
        if(count)count.textContent=(activeIndex+1)+' / '+slides.length;
        if(prev)prev.disabled=activeIndex===0;
        if(next)next.disabled=activeIndex===slides.length-1;
        if(focusTrack){
          try{
            track.focus({preventScroll:true});
          }catch(e){
            track.focus();
          }
        }
      }

      function scrollToIndex(index){
        setActive(index,true);
      }

      track.addEventListener('keydown',function(event){
        if(event.key==='ArrowLeft'){
          event.preventDefault();
          scrollToIndex(activeIndex-1);
        } else if(event.key==='ArrowRight'){
          event.preventDefault();
          scrollToIndex(activeIndex+1);
        } else if(event.key==='Home'){
          event.preventDefault();
          scrollToIndex(0);
        } else if(event.key==='End'){
          event.preventDefault();
          scrollToIndex(slides.length-1);
        }
      });

      if(prev)prev.addEventListener('click',function(){ scrollToIndex(activeIndex-1); });
      if(next)next.addEventListener('click',function(){ scrollToIndex(activeIndex+1); });

      carousel.querySelectorAll('[data-flip-card]').forEach(function(card){
        setCardFlipped(card,false);
      });

      carousel.querySelectorAll('[data-flip]').forEach(function(btn){
        btn.addEventListener('click',function(event){
          event.preventDefault();
          event.stopPropagation();
          var card=btn.closest('[data-flip-card]');
          if(card)setCardFlipped(card,!card.classList.contains('is-flipped'));
        });
      });

      carousel.querySelectorAll('[data-card-hit]').forEach(function(link){
        link.addEventListener('click',function(event){
          var slide=link.closest('[data-slide]');
          var index=slides.indexOf(slide);
          var card=link.closest('[data-flip-card]');
          if(index!==activeIndex){
            event.preventDefault();
            scrollToIndex(index);
            return;
          }
          if(dragMoved){
            event.preventDefault();
            return;
          }
          if(card)card.classList.add('is-launching');
        });
      });

      slides.forEach(function(slide,i){
        slide.addEventListener('click',function(event){
          if(event.target.closest('[data-flip]') || event.target.closest('[data-card-hit]'))return;
          if(i===activeIndex || dragMoved)return;
          event.preventDefault();
          scrollToIndex(i);
        });
      });

      track.addEventListener('pointerdown',function(event){
        if(event.button && event.button!==0)return;
        dragging=true;
        dragMoved=false;
        dragStartX=event.clientX;
        dragStartY=event.clientY;
        if(track.setPointerCapture){
          try{track.setPointerCapture(event.pointerId);}catch(e){}
        }
      });

      track.addEventListener('pointermove',function(event){
        if(!dragging)return;
        var dx=event.clientX-dragStartX;
        var dy=event.clientY-dragStartY;
        if(Math.abs(dx)>8 && Math.abs(dx)>Math.abs(dy))dragMoved=true;
      },{passive:true});

      function endDrag(event){
        if(!dragging)return;
        var dx=event.clientX-dragStartX;
        var dy=event.clientY-dragStartY;
        dragging=false;
        if(Math.abs(dx)>44 && Math.abs(dx)>Math.abs(dy)*1.2){
          scrollToIndex(activeIndex+(dx<0 ? 1 : -1));
        }
        setTimeout(function(){ dragMoved=false; },0);
      }

      track.addEventListener('pointerup',endDrag);
      track.addEventListener('pointercancel',function(){ dragging=false; dragMoved=false; });

      window.addEventListener('resize',function(){
        clearTimeout(resizeTimer);
        resizeTimer=setTimeout(function(){ setActive(activeIndex,false); },120);
      });

      carousel.classList.add('is-ready');
      setActive(0);
    });
  }

  cycleSignal();
  bindTapSounds();
  initCarousels();
})();
