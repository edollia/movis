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

  function lockPageZoom(){
    document.addEventListener('gesturestart',function(event){ event.preventDefault(); },{passive:false});
    document.addEventListener('gesturechange',function(event){ event.preventDefault(); },{passive:false});
    document.addEventListener('touchmove',function(event){
      if(event.touches && event.touches.length>1)event.preventDefault();
    },{passive:false});
  }

  function initPosterArt(){
    document.querySelectorAll('.poster-stage').forEach(function(stage){
      var img=stage.querySelector('[data-poster-img]');
      if(!img){
        stage.classList.add('poster-missing');
        return;
      }

      function markLoaded(){
        stage.classList.remove('poster-loading','poster-slow','poster-missing');
        stage.classList.add('poster-loaded');
      }

      function markMissing(){
        img.hidden=true;
        stage.classList.remove('poster-loading','poster-slow','poster-loaded','has-poster');
        stage.classList.add('poster-missing');
      }

      if(img.complete){
        if(img.naturalWidth>0){
          markLoaded();
        } else {
          markMissing();
        }
        return;
      }

      img.addEventListener('load',markLoaded,{once:true});
      img.addEventListener('error',markMissing,{once:true});
      setTimeout(function(){
        if(stage.classList.contains('poster-loading'))stage.classList.add('poster-slow');
      },1200);
    });
  }

  function syncCardControls(card){
    var active=card.classList.contains('is-active');
    card.querySelectorAll('[data-card-hit]').forEach(function(el){
      if(active){
        el.removeAttribute('tabindex');
      } else {
        el.setAttribute('tabindex','-1');
      }
    });
  }

  function clamp(value,min,max){
    return Math.max(min,Math.min(value,max));
  }

  function px(value){
    return Math.round(value*10)/10+'px';
  }

  function sampleCurve(values,value){
    var max=values.length-1;
    var clamped=clamp(value,0,max);
    var low=Math.floor(clamped);
    var high=Math.min(max,low+1);
    var mix=clamped-low;
    return values[low]+(values[high]-values[low])*mix;
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
      var dragLastX=0;
      var dragLastTime=0;
      var dragVelocityX=0;
      var dragProgress=0;
      var dragPointerId=null;
      var dragCaptureTarget=null;
      var dragStartTarget=null;
      var dragMetrics=null;
      var dragging=false;
      var dragMoved=false;
      var tapMoved=false;
      var suppressClickUntil=0;
      var resizeTimer=0;
      var wheelIdleTimer=0;
      var wheelAccum=0;
      var wheelFrame=0;
      var pendingWheelSteps=0;
      var rushTimer=0;
      var jumpTimer=0;
      var metricsCache=null;
      var layoutFrame=0;
      var queuedProgress=0;
      var queuedMotionLevel=0;
      var launching=false;

      if(!track || !slides.length)return;

      function deckMetrics(force){
        if(metricsCache && !force)return metricsCache;
        var stage=carousel.querySelector('[data-deck-stage]') || track;
        var stageWidth=stage.clientWidth || track.clientWidth || window.innerWidth;
        var card=slides[0].querySelector('[data-movie-card]');
        var cardWidth=slides[0].offsetWidth || (card ? card.offsetWidth : 0) || (card ? card.getBoundingClientRect().width : 360);
        var isMobile=window.matchMedia && window.matchMedia('(max-width: 760px)').matches;
        var spread=isMobile ? .34 : .48;
        var divisor=isMobile ? 3.4 : 2.55;
        var side=Math.min(cardWidth*spread,Math.max(isMobile ? 54 : 78,(stageWidth-cardWidth)/divisor));
        var swipeUnit=Math.max(side*1.22,cardWidth*(isMobile ? .42 : .38));
        metricsCache={side:side,cardWidth:cardWidth,swipeUnit:swipeUnit};
        return metricsCache;
      }

      function applySlidePosition(slide,delta,metrics,progress,motionLevel){
        var abs=Math.abs(delta);
        var sign=delta<0 ? -1 : delta>0 ? 1 : 0;
        var offsetMap=[0,1,1.58,2.04,2.48];
        var scaleMap=[1,.88,.78,.69,.64];
        var opacityMap=[1,.72,.42,.18,0];
        var blurMap=[0,.45,1.7,3.4,6];
        var yMap=[0,10,21,32,42];
        var rotateMap=[0,7,11,14,16];
        var capped=Math.min(abs,4);
        var motion=clamp(motionLevel || 0,0,1);
        var crossingLift=motion*Math.max(0,1-Math.abs(abs-.5)*2)*.14;
        var spreadLift=Math.min(abs,3)*.12+crossingLift;
        var scale=sampleCurve(scaleMap,capped);
        var y=sampleCurve(yMap,capped);
        var depth=-76*capped;
        var z=Math.round(720-capped*58);

        if(abs<.04)z=900;
        if(progress){
          var travel=Math.min(1,Math.abs(progress));
          if(delta*progress<0){
            z+=Math.round(110*travel);
          } else if(delta*progress>0){
            z-=Math.round(32*travel);
          }
        }

        slide.style.setProperty('--deck-x',px(sign*metrics.side*(sampleCurve(offsetMap,capped)+spreadLift)));
        slide.style.setProperty('--deck-y',px(y));
        slide.style.setProperty('--deck-r',(sign*-sampleCurve(rotateMap,capped))+'deg');
        slide.style.setProperty('--deck-s',Math.max(.56,scale));
        slide.style.setProperty('--deck-o',sampleCurve(opacityMap,capped));
        slide.style.setProperty('--deck-blur',px(sampleCurve(blurMap,capped)));
        slide.style.setProperty('--deck-depth',px(depth));
        slide.style.setProperty('--deck-z',String(z));
        slide.classList.toggle('is-visible',abs<=3.35);
        slide.classList.toggle('is-far',abs>3.35);
      }

      function applyDeckLayout(index,progress,motionLevel,metricsOverride){
        var metrics=metricsOverride || deckMetrics();
        slides.forEach(function(slide,i){
          var card=slide.querySelector('[data-movie-card]');
          var isActive=i===index;
          var settledDelta=i-index;
          var delta=i-index+progress;
          slide.classList.toggle('is-active-slide',isActive);
          slide.classList.toggle('is-jumpable-slide',!isActive && Math.abs(settledDelta)<=3);
          slide.setAttribute('aria-hidden',isActive ? 'false' : 'true');
          slide.setAttribute('data-pos',String(clamp(settledDelta,-4,4)));
          slide.setAttribute('data-slide-index',String(i));
          applySlidePosition(slide,delta,metrics,progress,motionLevel);
          if(card){
            card.classList.toggle('is-active',isActive);
            syncCardControls(card);
          }
        });
      }

      function markRushing(duration){
        carousel.classList.add('is-rushing');
        clearTimeout(rushTimer);
        rushTimer=setTimeout(function(){
          carousel.classList.remove('is-rushing');
        },duration || 220);
      }

      function cancelQueuedLayout(){
        if(!layoutFrame)return;
        cancelAnimationFrame(layoutFrame);
        layoutFrame=0;
      }

      function cancelQueuedWheel(){
        if(!wheelFrame)return;
        cancelAnimationFrame(wheelFrame);
        wheelFrame=0;
        pendingWheelSteps=0;
      }

      function queueDeckLayout(progress,motionLevel){
        queuedProgress=progress;
        queuedMotionLevel=motionLevel;
        dragProgress=progress;
        if(layoutFrame)return;
        layoutFrame=requestAnimationFrame(function(){
          layoutFrame=0;
          applyDeckLayout(activeIndex,queuedProgress,queuedMotionLevel,dragMetrics || deckMetrics());
        });
      }

      function setActive(index,focusTrack,fast){
        var nextIndex=clamp(index,0,slides.length-1);
        var changed=nextIndex!==activeIndex;
        var jumpDistance=Math.abs(nextIndex-activeIndex);
        cancelQueuedLayout();
        if(changed){
          carousel.setAttribute('data-jump',jumpDistance>1 || fast ? 'far' : 'near');
          clearTimeout(jumpTimer);
          jumpTimer=setTimeout(function(){
            carousel.removeAttribute('data-jump');
          },jumpDistance>1 || fast ? 340 : 240);
          markRushing(jumpDistance>1 || fast ? 300 : 220);
        }
        activeIndex=nextIndex;
        dragProgress=0;
        carousel.classList.remove('is-dragging');
        applyDeckLayout(activeIndex,0,0);
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

      function scrollToIndex(index,fast){
        setActive(index,true,fast);
      }

      function selectIndex(index,fast){
        setActive(index,false,fast);
      }

      function settleDeck(){
        setActive(activeIndex,false);
      }

      function launchCard(card,href){
        function go(){
          window.location.href=href;
        }
        if(launching){
          go();
          return;
        }
        launching=true;
        suppressClickUntil=Date.now()+800;
        var navTimer=setTimeout(go,360);

        try{
          carousel.classList.add('is-launching-deck');

          var overlay=document.createElement('div');
          overlay.className='launch-wipe';
          overlay.setAttribute('aria-hidden','true');

          if(card){
            var rect=card.getBoundingClientRect();
            if(rect.width && rect.height){
              var shell=document.createElement('div');
              var clone=card.cloneNode(true);

              card.classList.add('is-launch-source');
              clone.classList.add('is-launching');
              Array.prototype.forEach.call(clone.querySelectorAll('a'),function(link){
                link.removeAttribute('href');
                link.setAttribute('tabindex','-1');
              });

              shell.className='launch-card-shell';
              shell.style.left=px(rect.left);
              shell.style.top=px(rect.top);
              shell.style.width=px(rect.width);
              shell.style.height=px(rect.height);
              shell.style.setProperty('--launch-dx','0px');
              shell.style.setProperty('--launch-dy','-10px');
              shell.style.setProperty('--launch-scale','1.025');
              shell.style.setProperty('--launch-scale-end','.985');
              shell.appendChild(clone);
              overlay.appendChild(shell);
            }
          }

          overlay.insertAdjacentHTML('beforeend','<div class="launch-core"></div>');
          document.body.appendChild(overlay);
        }catch(e){
          clearTimeout(navTimer);
          go();
        }
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

      if(prev)prev.addEventListener('click',function(){ selectIndex(activeIndex-1,true); });
      if(next)next.addEventListener('click',function(){ selectIndex(activeIndex+1,true); });

      carousel.querySelectorAll('[data-movie-card]').forEach(function(card){
        syncCardControls(card);
      });

      carousel.querySelectorAll('[data-card-hit]').forEach(function(link){
        link.addEventListener('click',function(event){
          var slide=link.closest('[data-slide]');
          var index=slides.indexOf(slide);
          var card=link.closest('[data-movie-card]');
          if(Date.now()<suppressClickUntil || dragMoved){
            event.preventDefault();
            return;
          }
          if(index!==activeIndex){
            event.preventDefault();
            selectIndex(index,true);
            return;
          }
          if(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)return;
          event.preventDefault();
          try{
            launchCard(card,link.href);
          }catch(e){
            window.location.href=link.href;
          }
        });
      });

      track.addEventListener('click',function(event){
        if(Date.now()<suppressClickUntil || dragMoved){
          event.preventDefault();
          event.stopPropagation();
        }
      },true);

      slides.forEach(function(slide,i){
        slide.addEventListener('click',function(event){
          if(event.target.closest('[data-card-hit]'))return;
          if(i===activeIndex || dragMoved || Date.now()<suppressClickUntil)return;
          event.preventDefault();
          selectIndex(i,true);
        });
      });

      function handleTapTarget(target,event){
        if(!target || launching || Date.now()<suppressClickUntil)return false;
        if(event && (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey))return false;
        if(target.nodeType!==1)target=target.parentElement;
        if(!target || !target.closest)return false;

        var link=target.closest('[data-card-hit]');
        var slide=(link ? link.closest('[data-slide]') : target.closest('[data-slide]'));
        if(!slide)return false;

        var index=slides.indexOf(slide);
        if(index<0)return false;

        if(index!==activeIndex){
          suppressClickUntil=Date.now()+360;
          selectIndex(index,Math.abs(index-activeIndex)>1);
          return true;
        }

        link=link || slide.querySelector('[data-card-hit]');
        if(!link || !target.closest('[data-movie-card]'))return false;

        suppressClickUntil=Date.now()+1000;
        try{
          launchCard(slide.querySelector('[data-movie-card]'),link.href);
        }catch(e){
          window.location.href=link.href;
        }
        return true;
      }

      function releasePointer(event){
        if(!dragCaptureTarget || !dragCaptureTarget.releasePointerCapture)return;
        try{dragCaptureTarget.releasePointerCapture(event.pointerId);}catch(e){}
      }

      function beginDrag(event){
        if(event.isPrimary===false)return false;
        if(event.button && event.button!==0)return false;
        if(launching)return false;
        cancelQueuedWheel();
        dragging=true;
        dragMoved=false;
        tapMoved=false;
        dragProgress=0;
        dragVelocityX=0;
        dragPointerId=event.pointerId;
        dragCaptureTarget=event.currentTarget || track;
        dragStartTarget=event.target;
        dragMetrics=deckMetrics(true);
        dragStartX=event.clientX;
        dragStartY=event.clientY;
        dragLastX=event.clientX;
        dragLastTime=event.timeStamp || Date.now();
        if(dragCaptureTarget.setPointerCapture){
          try{dragCaptureTarget.setPointerCapture(event.pointerId);}catch(e){}
        }
        return true;
      }

      function moveDrag(event){
        if(!dragging)return;
        if(dragPointerId!==null && event.pointerId!==dragPointerId)return;
        var dx=event.clientX-dragStartX;
        var dy=event.clientY-dragStartY;
        var now=event.timeStamp || Date.now();
        var dt=Math.max(12,now-dragLastTime);
        var metrics=dragMetrics || deckMetrics();
        var progress=clamp(dx/metrics.swipeUnit,-2.85,2.85);

        dragVelocityX=(event.clientX-dragLastX)/dt;
        dragLastX=event.clientX;
        dragLastTime=now;

        if(!tapMoved && Math.sqrt(dx*dx+dy*dy)>7)tapMoved=true;
        if(!dragMoved && Math.abs(dx)>9 && Math.abs(dx)>Math.abs(dy)*1.14){
          dragMoved=true;
          carousel.classList.add('is-dragging');
          carousel.classList.remove('is-rushing');
        }
        if(!dragMoved)return;
        event.preventDefault();

        if((activeIndex===0 && progress>0) || (activeIndex===slides.length-1 && progress<0)){
          progress*=.24;
        }
        queueDeckLayout(progress,.78);
      }

      function finishDrag(event){
        if(!dragging)return null;
        if(dragPointerId!==null && event.pointerId!==dragPointerId)return null;
        var dx=event.clientX-dragStartX;
        var dy=event.clientY-dragStartY;
        var metrics=dragMetrics || deckMetrics();
        var finalProgress=clamp(dx/metrics.swipeUnit,-2.85,2.85);
        var pointerMoved=Math.sqrt(dx*dx+dy*dy)>7;
        var horizontalMoved=Math.abs(dx)>9 && Math.abs(dx)>Math.abs(dy)*1.14;
        var projected=-finalProgress+(-dragVelocityX*260/metrics.swipeUnit);
        var maxLeap=window.matchMedia && window.matchMedia('(max-width: 760px)').matches ? 4 : 5;
        var steps=0;
        var moved=dragMoved || horizontalMoved;
        var movedEnough=tapMoved || pointerMoved || moved;
        var tapTarget=dragStartTarget;

        dragging=false;
        cancelQueuedLayout();
        releasePointer(event);
        dragPointerId=null;
        dragCaptureTarget=null;
        dragStartTarget=null;
        dragMetrics=null;
        carousel.classList.remove('is-dragging');

        tapMoved=false;
        if(!moved){
          dragProgress=0;
          dragVelocityX=0;
          if(handleTapTarget(tapTarget,event))return true;
          if(movedEnough)suppressClickUntil=Date.now()+520;
          return false;
        }

        if(movedEnough)suppressClickUntil=Date.now()+520;
        if(Math.abs(dx)>Math.abs(dy)*1.05){
          steps=Math.round(projected);
          if(steps===0 && Math.abs(projected)>.22)steps=projected>0 ? 1 : -1;
          steps=clamp(steps,-maxLeap,maxLeap);
        }
        selectIndex(activeIndex+steps,Math.abs(steps)>1);
        setTimeout(function(){ dragMoved=false; },120);
        return true;
      }

      function cancelDrag(event){
        if(dragPointerId!==null && event.pointerId!==dragPointerId)return;
        var movedEnough=tapMoved || dragMoved;
        dragging=false;
        cancelQueuedLayout();
        dragMoved=false;
        tapMoved=false;
        dragProgress=0;
        dragVelocityX=0;
        dragPointerId=null;
        dragMetrics=null;
        dragStartTarget=null;
        releasePointer(event);
        dragCaptureTarget=null;
        carousel.classList.remove('is-dragging');
        if(movedEnough)suppressClickUntil=Date.now()+520;
        applyDeckLayout(activeIndex,0,0);
      }

      function bindPointerSurface(surface){
        if(!surface)return;
        surface.addEventListener('pointerdown',beginDrag);
        surface.addEventListener('pointermove',moveDrag,{passive:false});
        surface.addEventListener('pointerup',finishDrag);
        surface.addEventListener('pointercancel',cancelDrag);
        surface.addEventListener('lostpointercapture',function(event){
          if(dragging && dragPointerId===event.pointerId)cancelDrag(event);
        });
      }

      bindPointerSurface(track);
      track.addEventListener('dragstart',function(event){
        event.preventDefault();
      });

      function normalizedWheel(event){
        var dx=event.deltaX;
        var dy=event.deltaY;
        if(event.deltaMode===1){
          dx*=18;
          dy*=18;
        }
        if(event.deltaMode===2){
          dx*=window.innerWidth*.8;
          dy*=window.innerHeight*.8;
        }
        return {
          delta:Math.abs(dx)>Math.abs(dy) ? dx : dy,
          horizontal:Math.abs(dx)>Math.max(8,Math.abs(dy)*.62)
        };
      }

      function queueWheelSteps(steps){
        pendingWheelSteps=clamp(pendingWheelSteps+steps,-6,6);
        if(wheelFrame)return;
        wheelFrame=requestAnimationFrame(function(){
          var queued=pendingWheelSteps;
          wheelFrame=0;
          pendingWheelSteps=0;
          if(!queued)return;
          selectIndex(activeIndex+queued,Math.abs(queued)>1);
        });
      }

      function wheelTargetAllowed(target){
        if(!target)return true;
        if(target.nodeType!==1)target=target.parentElement;
        if(!target || !target.closest)return true;
        return !target.closest('[data-admin-panel],input,textarea,select,.results-search,.deck-controls,.signal,.idle-check');
      }

      function handleDeckWheel(event,globalGuard){
        if(event._movisDeckWheel || launching)return;
        if(globalGuard && carousel.contains(event.target))return;
        if(!wheelTargetAllowed(event.target))return;
        var info=normalizedWheel(event);
        if(Math.abs(info.delta)<4)return;
        if(globalGuard && !info.horizontal)return;
        event._movisDeckWheel=true;
        event.preventDefault();
        wheelAccum+=info.delta;
        clearTimeout(wheelIdleTimer);
        wheelIdleTimer=setTimeout(function(){
          wheelAccum=0;
        },110);
        var threshold=Math.max(42,deckMetrics().cardWidth*.14);
        var steps=wheelAccum>0 ? Math.floor(wheelAccum/threshold) : Math.ceil(wheelAccum/threshold);
        if(!steps)return;
        steps=clamp(steps,-6,6);
        wheelAccum-=steps*threshold;
        queueWheelSteps(steps);
      }

      carousel.addEventListener('wheel',function(event){
        handleDeckWheel(event,false);
      },{passive:false,capture:true});

      window.addEventListener('wheel',function(event){
        if(!document.body.classList.contains('results-page'))return;
        handleDeckWheel(event,true);
      },{passive:false,capture:true});

      window.addEventListener('resize',function(){
        clearTimeout(resizeTimer);
        resizeTimer=setTimeout(function(){
          metricsCache=null;
          setActive(activeIndex,false);
        },120);
      });

      setActive(0,false);
      requestAnimationFrame(function(){
        settleDeck();
        carousel.classList.add('is-ready');
        setTimeout(settleDeck,80);
      });
      window.addEventListener('load',function(){
        settleDeck();
        setTimeout(settleDeck,120);
      },{once:true});
    });
  }

  function initOwnerPanel(){
    var config=window.MOVIS_ADMIN_CONFIG || {};
    var client=null;
    var panel=null;
    var statusEl=null;
    var token='';
    var tapCount=0;
    var tapTimer=0;
    var lastTapAt=0;

    function adminConfigured(){
      return !!(config.enabled && config.supabaseUrl && config.supabaseAnonKey);
    }

    function cleanText(value){
      return (value || '').toString();
    }

    function setStatus(message,isError){
      if(!statusEl)return;
      statusEl.textContent=message || '';
      statusEl.classList.toggle('is-error',!!isError);
    }

    function setBusy(button,busy){
      if(!button)return;
      button.disabled=!!busy;
      button.classList.toggle('is-busy',!!busy);
    }

    function getClient(){
      if(client)return client;
      if(!window.supabase || !window.supabase.createClient)return null;
      client=window.supabase.createClient(config.supabaseUrl,config.supabaseAnonKey);
      return client;
    }

    function showLogin(){
      if(!panel)return;
      panel.querySelector('[data-admin-login]').hidden=false;
      panel.querySelector('[data-admin-settings]').hidden=true;
    }

    function showSettings(){
      if(!panel)return;
      panel.querySelector('[data-admin-login]').hidden=true;
      panel.querySelector('[data-admin-settings]').hidden=false;
    }

    function adminFetch(path,options){
      options=options || {};
      options.headers=options.headers || {};
      options.headers.Authorization='Bearer '+token;
      if(options.body && !options.headers['Content-Type'])options.headers['Content-Type']='application/json';
      return fetch(path,options).then(function(response){
        return response.json().catch(function(){ return {}; }).then(function(data){
          if(!response.ok || data.ok===false){
            throw new Error(data.error || data.message || 'Request failed.');
          }
          return data;
        });
      });
    }

    function fillSettings(data){
      var form=panel.querySelector('[data-admin-settings]');
      var settings=data.settings || {};
      form.elements.show_loading_screen.checked=!!settings.show_loading_screen;
      form.elements.loading_line_1.value=cleanText(settings.loading_line_1);
      form.elements.loading_line_2.value=cleanText(settings.loading_line_2);
      form.elements.show_signal_support.checked=!!settings.show_signal_support;
      form.elements.support_label.value=cleanText(settings.support_label);
      form.elements.support_handle.value=cleanText(settings.support_handle);
      form.elements.support_url.value=cleanText(settings.support_url);
      var owner=panel.querySelector('[data-admin-owner]');
      if(owner)owner.textContent=data.email ? 'signed in as '+data.email : 'signed in';
      var restart=panel.querySelector('[data-admin-restart]');
      if(restart)restart.disabled=!data.restart_configured;
      showSettings();
      setStatus('');
    }

    function readSettings(){
      var form=panel.querySelector('[data-admin-settings]');
      return {
        show_loading_screen:form.elements.show_loading_screen.checked,
        loading_line_1:form.elements.loading_line_1.value,
        loading_line_2:form.elements.loading_line_2.value,
        show_signal_support:form.elements.show_signal_support.checked,
        support_label:form.elements.support_label.value,
        support_handle:form.elements.support_handle.value,
        support_url:form.elements.support_url.value
      };
    }

    function loadSettings(){
      setStatus('checking access...');
      return adminFetch('/api/admin/settings',{method:'GET'})
        .then(fillSettings)
        .catch(function(error){
          token='';
          showLogin();
          setStatus(error.message,true);
        });
    }

    function bootstrapSession(){
      if(!adminConfigured()){
        showLogin();
        setStatus('Supabase is not configured on this server yet.',true);
        return;
      }
      var supa=getClient();
      if(!supa){
        showLogin();
        setStatus('Supabase client did not load.',true);
        return;
      }
      supa.auth.getSession().then(function(result){
        var session=result && result.data ? result.data.session : null;
        if(!session){
          showLogin();
          setStatus('');
          return;
        }
        token=session.access_token;
        loadSettings();
      }).catch(function(error){
        showLogin();
        setStatus(error && error.message ? error.message : 'Could not read Supabase session.',true);
      });
    }

    function ensurePanel(){
      if(panel)return panel;
      panel=document.createElement('div');
      panel.className='admin-panel';
      panel.setAttribute('data-admin-panel','');
      panel.hidden=true;
      panel.innerHTML=[
        '<div class="admin-shell" role="dialog" aria-modal="true" aria-label="Owner controls">',
        '<button class="admin-close" type="button" data-admin-close aria-label="Close">x</button>',
        '<p class="admin-kicker">owner panel</p>',
        '<h2>settings</h2>',
        '<form class="admin-login" data-admin-login>',
        '<label>email<input type="email" name="email" autocomplete="email" required></label>',
        '<label>password<input type="password" name="password" autocomplete="current-password" required></label>',
        '<button type="submit">sign in</button>',
        '</form>',
        '<form class="admin-settings" data-admin-settings hidden>',
        '<p class="admin-owner" data-admin-owner></p>',
        '<label class="admin-toggle"><input type="checkbox" name="show_loading_screen"><span>loading screen</span></label>',
        '<label>loading line 1<input type="text" name="loading_line_1" maxlength="80"></label>',
        '<label>loading line 2<input type="text" name="loading_line_2" maxlength="80"></label>',
        '<label class="admin-toggle"><input type="checkbox" name="show_signal_support"><span>signal / support badge</span></label>',
        '<label>support label<input type="text" name="support_label" maxlength="28"></label>',
        '<label>support handle<input type="text" name="support_handle" maxlength="42"></label>',
        '<label>support url<input type="url" name="support_url" maxlength="300"></label>',
        '<div class="admin-actions">',
        '<button type="submit" data-admin-save>save</button>',
        '<button type="button" data-admin-cache>clear cache</button>',
        '<button type="button" data-admin-restart>restart server</button>',
        '<button type="button" data-admin-logout>logout</button>',
        '</div>',
        '</form>',
        '<p class="admin-status" data-admin-status></p>',
        '</div>'
      ].join('');
      document.body.appendChild(panel);
      statusEl=panel.querySelector('[data-admin-status]');
      if(!adminConfigured()){
        panel.querySelectorAll('[data-admin-login] input,[data-admin-login] button').forEach(function(el){
          el.disabled=true;
        });
      }

      panel.addEventListener('click',function(event){
        if(event.target===panel || event.target.closest('[data-admin-close]'))closePanel();
      });

      panel.querySelector('[data-admin-login]').addEventListener('submit',function(event){
        event.preventDefault();
        var supa=getClient();
        var button=event.target.querySelector('button[type="submit"]');
        if(!supa){
          setStatus('Supabase client did not load.',true);
          return;
        }
        setBusy(button,true);
        setStatus('signing in...');
        supa.auth.signInWithPassword({
          email:event.target.elements.email.value,
          password:event.target.elements.password.value
        }).then(function(result){
          setBusy(button,false);
          if(result.error){
            setStatus(result.error.message || 'Could not sign in.',true);
            return;
          }
          if(!result.data || !result.data.session || !result.data.session.access_token){
            setStatus('Supabase did not return a session.',true);
            return;
          }
          token=result.data.session.access_token;
          event.target.elements.password.value='';
          loadSettings();
        }).catch(function(error){
          setBusy(button,false);
          setStatus(error && error.message ? error.message : 'Could not sign in.',true);
        });
      });

      panel.querySelector('[data-admin-settings]').addEventListener('submit',function(event){
        event.preventDefault();
        var button=panel.querySelector('[data-admin-save]');
        setBusy(button,true);
        setStatus('saving...');
        adminFetch('/api/admin/settings',{
          method:'POST',
          body:JSON.stringify(readSettings())
        }).then(function(){
          setBusy(button,false);
          setStatus('saved. reloading...');
          setTimeout(function(){ window.location.reload(); },650);
        }).catch(function(error){
          setBusy(button,false);
          setStatus(error.message,true);
        });
      });

      panel.querySelector('[data-admin-cache]').addEventListener('click',function(event){
        var button=event.currentTarget;
        setBusy(button,true);
        setStatus('clearing cache...');
        adminFetch('/api/admin/cache/clear',{method:'POST'})
          .then(function(data){
            setBusy(button,false);
            setStatus('cache cleared: '+data.cleared+' entries');
          })
          .catch(function(error){
            setBusy(button,false);
            setStatus(error.message,true);
          });
      });

      panel.querySelector('[data-admin-restart]').addEventListener('click',function(event){
        var button=event.currentTarget;
        setBusy(button,true);
        setStatus('requesting restart...');
        adminFetch('/api/admin/server/restart',{method:'POST'})
          .then(function(data){
            setBusy(button,false);
            setStatus(data.message || 'restart requested');
          })
          .catch(function(error){
            setBusy(button,false);
            setStatus(error.message,true);
          });
      });

      panel.querySelector('[data-admin-logout]').addEventListener('click',function(){
        var supa=getClient();
        token='';
        if(supa)supa.auth.signOut();
        showLogin();
        setStatus('signed out');
      });

      return panel;
    }

    function openPanel(){
      ensurePanel();
      panel.hidden=false;
      document.body.classList.add('admin-open');
      bootstrapSession();
      setTimeout(function(){
        var first=panel.querySelector('input,button');
        if(first)first.focus({preventScroll:true});
      },0);
    }

    function closePanel(){
      if(!panel)return;
      panel.hidden=true;
      document.body.classList.remove('admin-open');
    }

    function isBackgroundTap(target){
      if(!target || target.nodeType!==1)return false;
      return !target.closest([
        'a','button','input','textarea','select','label',
        '[data-admin-panel]','[data-carousel]','.home-search','.results-search',
        '.signal','.idle-check','.movie-card','.deck-controls'
      ].join(','));
    }

    function registerSecretTap(event){
      var now=Date.now();
      if(now-lastTapAt<140)return;
      lastTapAt=now;
      if(event && event.type==='pointerup' && event.pointerType==='mouse' && event.button!==0)return;
      if(event && event.type==='click' && event.button!==0)return;
      if(!isBackgroundTap(event.target))return;
      tapCount++;
      clearTimeout(tapTimer);
      if(tapCount>=5){
        tapCount=0;
        openPanel();
        return;
      }
      tapTimer=setTimeout(function(){ tapCount=0; },2200);
    }

    document.addEventListener('pointerup',registerSecretTap);
    document.addEventListener('click',registerSecretTap);
    document.addEventListener('touchend',function(event){
      if(event.touches && event.touches.length)return;
      registerSecretTap(event);
    },{passive:true});

    document.addEventListener('keydown',function(event){
      if(event.key==='Escape')closePanel();
    });
  }

  cycleSignal();
  bindTapSounds();
  lockPageZoom();
  initPosterArt();
  initCarousels();
  initOwnerPanel();
})();
