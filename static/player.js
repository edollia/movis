(function(){
  'use strict';

  var root=document.querySelector('[data-media-player]');
  if(!root)return;

  var frame=root.querySelector('[data-provider-frame]');
  var loading=root.querySelector('[data-player-loading]');
  var status=root.querySelector('[data-player-status]');
  var seasonPicker=root.querySelector('[data-season-picker]');
  var episodePicker=root.querySelector('[data-episode-picker-input]');
  var pickerForm=root.querySelector('[data-episode-picker]');
  var reloadButton=root.querySelector('[data-reload-player]');
  var fullscreenButton=root.querySelector('[data-fullscreen-player]');
  var fullscreenLabel=root.querySelector('[data-fullscreen-label]');
  var fullscreenTarget=root.querySelector('[data-player-fullscreen-target]');
  var pseudoFullscreen=false;
  var fullscreenCheckTimer=0;
  var loadTimer=0;
  var providerOrigin='https://player.vidlove.cc';

  function providerProgress(data){
    if(!data || typeof data!=='object')return null;
    if(data.type==='WATCH_PROGRESS' && data.data && typeof data.data.currentTime==='number'){
      return {time:data.data.currentTime,event:String(data.data.eventType||'timeupdate').toLowerCase()};
    }
    if(data.type==='PLAYER_EVENT' && data.data){
      return {time:typeof data.data.currentTime==='number'?data.data.currentTime:0,event:String(data.data.event||'').toLowerCase()};
    }
    if(data.type==='MEDIA_DATA' && data.data && data.data.progress){
      return {time:Number(data.data.progress.watched)||0,event:'timeupdate'};
    }
    return null;
  }

  function setStatus(message,ready){
    if(status){
      status.lastChild.textContent=' '+message;
      status.classList.toggle('is-ready',!!ready);
    }
    if(loading)loading.classList.toggle('is-hidden',!!ready);
  }

  function metadataParams(){
    var params=new URLSearchParams();
    ['title','year','poster'].forEach(function(key){
      var value=root.getAttribute('data-'+key);
      if(value)params.set(key,value);
    });
    return params.toString();
  }

  function episodeUrl(season,episode){
    season=Math.max(1,Math.min(999,Number(season)||1));
    episode=Math.max(1,Math.min(9999,Number(episode)||1));
    var url='/watch-tv/'+encodeURIComponent(root.dataset.tmdbId)+'/'+season+'/'+episode;
    var query=metadataParams();
    return query ? url+'?'+query : url;
  }

  function navigate(season,episode){
    window.location.assign(episodeUrl(season,episode));
  }

  if(frame){
    loadTimer=window.setTimeout(function(){
      setStatus('still connecting — try reload if this continues',false);
    },12000);
    frame.addEventListener('load',function(){
      window.clearTimeout(loadTimer);
      setStatus('ready • press play',true);
    });
  }

  window.addEventListener('message',function(event){
    if(event.origin!==providerOrigin || !frame || event.source!==frame.contentWindow)return;
    var progress=providerProgress(event.data);
    if(!progress)return;
    if(progress.event==='playing' || progress.event==='play' || progress.time>0){
      setStatus('playing',true);
    }
  });

  if(pickerForm){
    pickerForm.addEventListener('submit',function(event){
      event.preventDefault();
      navigate(seasonPicker.value,episodePicker.value);
    });
  }

  if(seasonPicker){
    seasonPicker.addEventListener('change',function(){
      navigate(seasonPicker.value,1);
    });
  }

  if(episodePicker && episodePicker.tagName==='SELECT'){
    episodePicker.addEventListener('change',function(){
      navigate(seasonPicker.value,episodePicker.value);
    });
  }

  if(reloadButton && frame){
    reloadButton.addEventListener('click',function(){
      var source=frame.src;
      setStatus('reconnecting',false);
      frame.src='about:blank';
      window.requestAnimationFrame(function(){frame.src=source;});
    });
  }

  function currentFullscreenElement(){
    return document.fullscreenElement || document.webkitFullscreenElement || null;
  }

  function syncFullscreenButton(){
    if(!fullscreenButton)return;
    var active=currentFullscreenElement()===fullscreenTarget || pseudoFullscreen;
    var label=active ? 'Exit fullscreen' : 'Enter fullscreen';
    fullscreenButton.setAttribute('aria-label',label);
    fullscreenButton.setAttribute('title',label);
    fullscreenButton.setAttribute('aria-pressed',active ? 'true' : 'false');
    fullscreenButton.classList.toggle('is-active',active);
    if(fullscreenLabel)fullscreenLabel.textContent=active ? 'exit' : 'fullscreen';
  }

  function setPseudoFullscreen(active){
    pseudoFullscreen=!!active;
    fullscreenTarget.classList.toggle('is-pseudo-fullscreen',pseudoFullscreen);
    document.body.classList.toggle('has-pseudo-fullscreen',pseudoFullscreen);
    syncFullscreenButton();
  }

  function enterPseudoFullscreen(){
    if(!currentFullscreenElement())setPseudoFullscreen(true);
  }

  if(fullscreenButton && fullscreenTarget){
    fullscreenButton.addEventListener('click',function(){
      window.clearTimeout(fullscreenCheckTimer);
      if(currentFullscreenElement()===fullscreenTarget){
        var exit=document.exitFullscreen || document.webkitExitFullscreen;
        if(exit)exit.call(document);
        return;
      }
      if(pseudoFullscreen){
        setPseudoFullscreen(false);
        return;
      }
      var enter=fullscreenTarget.requestFullscreen || fullscreenTarget.webkitRequestFullscreen;
      if(enter){
        try{
          var request=enter.call(fullscreenTarget);
          if(request && request.catch)request.catch(enterPseudoFullscreen);
          fullscreenCheckTimer=window.setTimeout(enterPseudoFullscreen,500);
        }catch(e){enterPseudoFullscreen();}
      }else{
        enterPseudoFullscreen();
      }
    });
    function onFullscreenChange(){
      window.clearTimeout(fullscreenCheckTimer);
      if(currentFullscreenElement())setPseudoFullscreen(false);
      syncFullscreenButton();
    }
    document.addEventListener('fullscreenchange',onFullscreenChange);
    document.addEventListener('webkitfullscreenchange',onFullscreenChange);
    syncFullscreenButton();
  }

  document.addEventListener('keydown',function(event){
    var target=event.target;
    if(target && /INPUT|SELECT|TEXTAREA/.test(target.tagName))return;
    if(event.key==='Escape' && pseudoFullscreen)setPseudoFullscreen(false);
    if((event.key==='r' || event.key==='R') && reloadButton)reloadButton.click();
  });

  root.dataset.controlsReady='true';
}());
