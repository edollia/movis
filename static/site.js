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

  function toggleFaceControls(face, enabled){
    if(!face)return;
    face.querySelectorAll('a,button,input,select,textarea').forEach(function(el){
      if(enabled){
        el.removeAttribute('tabindex');
      } else {
        el.setAttribute('tabindex','-1');
      }
    });
  }

  function setCardFlipped(card, flipped){
    var front=card.querySelector('.movie-front');
    var back=card.querySelector('.movie-back');
    card.classList.toggle('is-flipped',flipped);
    if(front)front.setAttribute('aria-hidden',flipped ? 'true' : 'false');
    if(back)back.setAttribute('aria-hidden',flipped ? 'false' : 'true');
    toggleFaceControls(front,!flipped);
    toggleFaceControls(back,flipped);
    card.querySelectorAll('[data-flip]').forEach(function(btn){
      btn.setAttribute('aria-pressed',flipped ? 'true' : 'false');
    });
  }

  function initCarousels(){
    document.querySelectorAll('[data-carousel]').forEach(function(carousel){
      var track=carousel.querySelector('[data-carousel-track]');
      var slides=Array.prototype.slice.call(carousel.querySelectorAll('[data-slide]'));
      var prev=carousel.querySelector('[data-carousel-prev]');
      var next=carousel.querySelector('[data-carousel-next]');
      var count=carousel.querySelector('[data-carousel-count]');
      var activeIndex=0;
      var ticking=false;

      if(!track || !slides.length)return;

      function setActive(index){
        activeIndex=Math.max(0,Math.min(index,slides.length-1));
        slides.forEach(function(slide,i){
          var card=slide.querySelector('[data-flip-card]');
          if(card)card.classList.toggle('is-active',i===activeIndex);
        });
        if(count)count.textContent=(activeIndex+1)+' / '+slides.length;
        if(prev)prev.disabled=activeIndex===0;
        if(next)next.disabled=activeIndex===slides.length-1;
      }

      function nearestIndex(){
        var center=track.scrollLeft+(track.clientWidth/2);
        var bestIndex=0;
        var bestDistance=Infinity;
        slides.forEach(function(slide,i){
          var slideCenter=slide.offsetLeft+(slide.offsetWidth/2);
          var distance=Math.abs(center-slideCenter);
          if(distance<bestDistance){
            bestDistance=distance;
            bestIndex=i;
          }
        });
        return bestIndex;
      }

      function scrollToIndex(index){
        var slide=slides[Math.max(0,Math.min(index,slides.length-1))];
        if(!slide)return;
        var left=slide.offsetLeft-((track.clientWidth-slide.offsetWidth)/2);
        try{
          track.scrollTo({left:left,behavior:'smooth'});
        }catch(e){
          track.scrollLeft=left;
        }
        setActive(index);
      }

      track.addEventListener('scroll',function(){
        if(ticking)return;
        ticking=true;
        requestAnimationFrame(function(){
          setActive(nearestIndex());
          ticking=false;
        });
      },{passive:true});

      track.addEventListener('keydown',function(event){
        if(event.key==='ArrowLeft'){
          event.preventDefault();
          scrollToIndex(activeIndex-1);
        }
        if(event.key==='ArrowRight'){
          event.preventDefault();
          scrollToIndex(activeIndex+1);
        }
      });

      if(prev)prev.addEventListener('click',function(){ scrollToIndex(activeIndex-1); });
      if(next)next.addEventListener('click',function(){ scrollToIndex(activeIndex+1); });

      carousel.querySelectorAll('[data-flip-card]').forEach(function(card){
        setCardFlipped(card,false);
      });

      carousel.querySelectorAll('[data-flip]').forEach(function(btn){
        btn.addEventListener('click',function(){
          var card=btn.closest('[data-flip-card]');
          if(card)setCardFlipped(card,!card.classList.contains('is-flipped'));
        });
      });

      carousel.querySelectorAll('[data-launch]').forEach(function(link){
        link.addEventListener('click',function(){
          var card=link.closest('[data-flip-card]');
          if(card)card.classList.add('is-launching');
        });
      });

      setActive(0);
      carousel.classList.add('is-ready');
    });
  }

  cycleSignal();
  bindTapSounds();
  initCarousels();
})();
