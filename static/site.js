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

  cycleSignal();
  bindTapSounds();
})();
