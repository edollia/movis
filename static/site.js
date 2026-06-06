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
      var wheelTimer=0;
      var wheelIdleTimer=0;
      var wheelLocked=false;
      var wheelAccum=0;

      if(!track || !slides.length)return;

      function deckMetrics(){
        var stage=carousel.querySelector('[data-deck-stage]') || track;
        var stageWidth=stage.clientWidth || track.clientWidth || window.innerWidth;
        var card=slides[0].querySelector('[data-movie-card]');
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
          var card=slide.querySelector('[data-movie-card]');
          var isActive=i===activeIndex;
          var delta=i-activeIndex;
          slide.classList.toggle('is-active-slide',isActive);
          slide.setAttribute('aria-hidden',isActive ? 'false' : 'true');
          applySlidePosition(slide,delta,metrics);
          if(card){
            card.classList.toggle('is-active',isActive);
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

      function settleDeck(){
        setActive(activeIndex,false);
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

      carousel.querySelectorAll('[data-movie-card]').forEach(function(card){
        syncCardControls(card);
      });

      carousel.querySelectorAll('[data-card-hit]').forEach(function(link){
        link.addEventListener('click',function(event){
          var slide=link.closest('[data-slide]');
          var index=slides.indexOf(slide);
          var card=link.closest('[data-movie-card]');
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
          if(event.target.closest('[data-card-hit]'))return;
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

      track.addEventListener('wheel',function(event){
        var delta=Math.abs(event.deltaX)>Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
        if(Math.abs(delta)<4)return;
        event.preventDefault();
        wheelAccum+=delta;
        clearTimeout(wheelIdleTimer);
        wheelIdleTimer=setTimeout(function(){
          wheelAccum=0;
          wheelLocked=false;
        },180);
        if(wheelLocked || Math.abs(wheelAccum)<92)return;
        wheelLocked=true;
        scrollToIndex(activeIndex+(wheelAccum>0 ? 1 : -1));
        wheelAccum=0;
        clearTimeout(wheelTimer);
        wheelTimer=setTimeout(function(){ wheelLocked=false; },460);
      },{passive:false});

      window.addEventListener('resize',function(){
        clearTimeout(resizeTimer);
        resizeTimer=setTimeout(function(){ setActive(activeIndex,false); },120);
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
          token=result.data.session.access_token;
          event.target.elements.password.value='';
          loadSettings();
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
  initCarousels();
  initOwnerPanel();
})();
