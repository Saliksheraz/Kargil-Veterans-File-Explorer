/**
 * 360 Degree Panoramic Video Player for Kargil Veterans File Explorer
 * Uses Three.js for interactive equirectangular spherical WebGL projection.
 * Supports touch drag, mouse drag, inertia, zoom, auto-rotation, compass heading,
 * seamless 360/Flat 2D mode toggling, and complete playback controls.
 */

(function (window, document) {
    'use strict';

    // Helper: Detect if a filename represents a 360-degree / VR video
    function is360Video(filename) {
        if (!filename) return false;
        var name = filename.toLowerCase();
        return Boolean(name.match(/(360|360vr|vr360|_vr|\bvr\b|equirectangular|panoramic|spherical|panorama|360video)/i));
    }

    // Helper: Format seconds to MM:SS or HH:MM:SS
    function formatTime(seconds) {
        if (isNaN(seconds) || seconds < 0) return '00:00';
        var sec = Math.floor(seconds);
        var h = Math.floor(sec / 3600);
        var m = Math.floor((sec % 3600) / 60);
        var s = sec % 60;
        if (h > 0) {
            return (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
        }
        return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
    }

    // Main Player Factory
    function init360VideoPlayer(container, videoUrl, options) {
        options = options || {};
        var title = options.title || 'Video Player';
        var is360Mode = (typeof options.is360Default === 'boolean') ? options.is360Default : is360Video(title);
        var autoPlay = options.autoPlay !== false;

        // Ensure container is empty and styled
        container.innerHTML = '';

        // Build Player HTML structure
        var wrapper = document.createElement('div');
        wrapper.className = 'video360-wrapper';
        wrapper.tabIndex = 0; // for keyboard focus

        wrapper.innerHTML = [
            '<div class="video360-canvas-container"></div>',
            '<div class="video360-flat-container" style="display: none;"></div>',
            '<div class="video360-top-bar">',
            '    <div class="video360-badge-group">',
            '        <span class="video360-badge mode-badge">',
            '            <i class="bi bi-badge-vr-fill"></i> <span class="badge-text">' + (is360Mode ? '360° Sphere Mode' : 'Standard 2D Mode') + '</span>',
            '        </span>',
            '        <button type="button" class="video360-compass-btn" title="Click to Reset View to Center (0° N)">',
            '            <i class="bi bi-compass-fill video360-compass-icon text-warning"></i>',
            '            <span class="compass-text">0° N</span>',
            '        </button>',
            '    </div>',
            '</div>',
            '<div class="video360-hint-overlay">',
            '    <i class="bi bi-arrows-move text-warning fs-5"></i>',
            '    <span>Drag to look 360° &bull; Scroll / Pinch to zoom</span>',
            '</div>',
            '<div class="video360-center-play" title="Play">',
            '    <i class="bi bi-play-fill"></i>',
            '</div>',
            '<div class="video360-controls-bar">',
            '    <div class="video360-progress-container">',
            '        <div class="video360-progress-bg">',
            '            <div class="video360-progress-buffer"></div>',
            '            <div class="video360-progress-played"></div>',
            '            <div class="video360-progress-thumb"></div>',
            '        </div>',
            '        <div class="video360-time-tooltip">00:00</div>',
            '    </div>',
            '    <div class="video360-buttons-row">',
            '        <div class="video360-buttons-left">',
            '            <button type="button" class="video360-btn btn-play" title="Play / Pause (Space)">',
            '                <i class="bi bi-play-fill"></i>',
            '            </button>',
            '            <div class="video360-volume-box">',
            '                <button type="button" class="video360-btn btn-volume" title="Mute / Unmute (M)">',
            '                    <i class="bi bi-volume-up-fill"></i>',
            '                </button>',
            '                <input type="range" class="video360-volume-slider" min="0" max="1" step="0.05" value="1" title="Volume">',
            '            </div>',
            '            <div class="video360-time-display">',
            '                <span class="current-time">00:00</span> / <span class="total-duration">00:00</span>',
            '            </div>',
            '        </div>',
            '        <div class="video360-buttons-right">',
            '            <div class="video360-mode-toggle" title="Switch Projection Mode">',
            '                <button type="button" class="video360-mode-btn btn-mode-360 ' + (is360Mode ? 'active' : '') + '">',
            '                    <i class="bi bi-badge-vr"></i> 360°',
            '                </button>',
            '                <button type="button" class="video360-mode-btn btn-mode-flat ' + (!is360Mode ? 'active' : '') + '">',
            '                    <i class="bi bi-aspect-ratio"></i> Flat',
            '                </button>',
            '            </div>',
            '            <button type="button" class="video360-btn btn-auto-rotate" title="Toggle Auto-Rotation">',
            '                <i class="bi bi-arrow-repeat"></i>',
            '            </button>',
            '            <button type="button" class="video360-btn btn-reset-view" title="Reset View to Front (R)">',
            '                <i class="bi bi-crosshair"></i>',
            '            </button>',
            '            <button type="button" class="video360-btn video360-speed-btn" title="Playback Speed">1x</button>',
            '            <button type="button" class="video360-btn btn-fullscreen" title="Fullscreen (F)">',
            '                <i class="bi bi-arrows-fullscreen"></i>',
            '            </button>',
            '        </div>',
            '    </div>',
            '</div>'
        ].join('\n');

        container.appendChild(wrapper);

        // Elements
        var canvasContainer = wrapper.querySelector('.video360-canvas-container');
        var flatContainer = wrapper.querySelector('.video360-flat-container');
        var topBar = wrapper.querySelector('.video360-top-bar');
        var modeBadge = wrapper.querySelector('.mode-badge');
        var badgeText = wrapper.querySelector('.badge-text');
        var compassBtn = wrapper.querySelector('.video360-compass-btn');
        var compassIcon = wrapper.querySelector('.video360-compass-icon');
        var compassText = wrapper.querySelector('.compass-text');
        var hintOverlay = wrapper.querySelector('.video360-hint-overlay');
        var centerPlayBtn = wrapper.querySelector('.video360-center-play');
        var controlsBar = wrapper.querySelector('.video360-controls-bar');
        var progressContainer = wrapper.querySelector('.video360-progress-container');
        var progressBuffer = wrapper.querySelector('.video360-progress-buffer');
        var progressPlayed = wrapper.querySelector('.video360-progress-played');
        var progressThumb = wrapper.querySelector('.video360-progress-thumb');
        var timeTooltip = wrapper.querySelector('.video360-time-tooltip');
        var btnPlay = wrapper.querySelector('.btn-play');
        var btnVolume = wrapper.querySelector('.btn-volume');
        var volumeSlider = wrapper.querySelector('.video360-volume-slider');
        var currentTimeEl = wrapper.querySelector('.current-time');
        var totalDurationEl = wrapper.querySelector('.total-duration');
        var btnMode360 = wrapper.querySelector('.btn-mode-360');
        var btnModeFlat = wrapper.querySelector('.btn-mode-flat');
        var btnAutoRotate = wrapper.querySelector('.btn-auto-rotate');
        var btnResetView = wrapper.querySelector('.btn-reset-view');
        var btnSpeed = wrapper.querySelector('.video360-speed-btn');
        var btnFullscreen = wrapper.querySelector('.btn-fullscreen');

        // Master HTML5 Video Element - persistently placed inside flatContainer
        var video = document.createElement('video');
        video.crossOrigin = 'anonymous';
        video.playsInline = true;
        video.preload = 'auto';
        video.src = videoUrl;
        flatContainer.appendChild(video);

        // Clicking directly on flat video toggles play/pause
        video.addEventListener('click', function (e) {
            e.stopPropagation();
            togglePlay();
        });

        // Three.js instances
        var scene, camera, renderer, mesh, geometry, material, texture;
        var animationFrameId = null;
        var isDestroyed = false;

        // Spherical Navigation Variables
        var lon = 0;
        var lat = 0;
        var phi = 0;
        var theta = 0;
        var target = null;
        var cameraFov = 75;

        // Drag & Inertia Variables
        var isUserInteracting = false;
        var pointerStartX = 0;
        var pointerStartY = 0;
        var pointerMoved = false;
        var onPointerDownLon = 0;
        var onPointerDownLat = 0;
        var velLon = 0;
        var velLat = 0;
        var lastPointerX = 0;
        var lastPointerY = 0;
        var isAutoRotating = false;

        // Pinch to zoom state
        var initialPinchDistance = null;
        var initialFov = 75;

        // Inactivity Timer for controls
        var controlsTimeout = null;

        function showControls() {
            controlsBar.classList.remove('video360-controls-hidden');
            topBar.style.opacity = '1';
            clearTimeout(controlsTimeout);
            if (!video.paused) {
                controlsTimeout = setTimeout(function () {
                    controlsBar.classList.add('video360-controls-hidden');
                    topBar.style.opacity = '0';
                }, 3500);
            }
        }

        // Initialize Three.js WebGL Scene
        function initThreeJS() {
            if (!window.THREE) {
                console.error('[Video360] Three.js library is missing! Falling back to 2D.');
                setMode(false);
                return;
            }

            if (renderer) return; // already initialized

            var width = canvasContainer.clientWidth || wrapper.clientWidth || 800;
            var height = canvasContainer.clientHeight || wrapper.clientHeight || 500;

            scene = new THREE.Scene();
            camera = new THREE.PerspectiveCamera(cameraFov, width / height, 0.1, 1100);
            target = new THREE.Vector3();

            renderer = new THREE.WebGLRenderer({
                antialias: true,
                alpha: false,
                powerPreference: 'high-performance'
            });
            renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
            renderer.setSize(width, height);
            canvasContainer.appendChild(renderer.domElement);

            // Inverted Equirectangular Sphere: camera sits at origin (0,0,0) and looks inside
            geometry = new THREE.SphereGeometry(500, 60, 40);
            geometry.scale(-1, 1, 1);

            texture = new THREE.VideoTexture(video);
            texture.minFilter = THREE.LinearFilter;
            texture.magFilter = THREE.LinearFilter;
            texture.format = THREE.RGBFormat;

            material = new THREE.MeshBasicMaterial({ map: texture });
            mesh = new THREE.Mesh(geometry, material);
            scene.add(mesh);

            // Start animation render loop
            animate();
        }

        function animate() {
            if (isDestroyed) return;
            animationFrameId = requestAnimationFrame(animate);

            if (!is360Mode) return;

            // Damping / Inertia
            if (!isUserInteracting) {
                if (isAutoRotating && !video.paused) {
                    lon += 0.08;
                } else {
                    lon += velLon;
                    lat += velLat;
                    velLon *= 0.92;
                    velLat *= 0.92;
                    if (Math.abs(velLon) < 0.001) velLon = 0;
                    if (Math.abs(velLat) < 0.001) velLat = 0;
                }
            }

            // Clamp latitude to avoid pole flipping
            lat = Math.max(-85, Math.min(85, lat));

            phi = THREE.MathUtils.degToRad(90 - lat);
            theta = THREE.MathUtils.degToRad(lon);

            target.x = 500 * Math.sin(phi) * Math.cos(theta);
            target.y = 500 * Math.cos(phi);
            target.z = 500 * Math.sin(phi) * Math.sin(theta);

            camera.lookAt(target);

            if (renderer && scene && camera) {
                renderer.render(scene, camera);
            }

            updateCompassUI();
        }

        // Compass heading calculator
        function updateCompassUI() {
            var normLon = ((-lon % 360) + 360) % 360;
            var deg = Math.round(normLon);
            var cardinal = 'N';
            if (deg >= 23 && deg < 68) cardinal = 'NE';
            else if (deg >= 68 && deg < 113) cardinal = 'E';
            else if (deg >= 113 && deg < 158) cardinal = 'SE';
            else if (deg >= 158 && deg < 203) cardinal = 'S';
            else if (deg >= 203 && deg < 248) cardinal = 'SW';
            else if (deg >= 248 && deg < 293) cardinal = 'W';
            else if (deg >= 293 && deg < 338) cardinal = 'NW';

            compassText.textContent = deg + '° ' + cardinal;
            compassIcon.style.transform = 'rotate(' + (normLon) + 'deg)';
        }

        // Smooth Reset View Animation
        function resetView() {
            var startLon = lon;
            var startLat = lat;
            var startFov = camera ? camera.fov : 75;
            var targetLon = 0;
            var targetLat = 0;
            var targetFov = 75;
            var startTime = performance.now();
            var duration = 400; // ms

            function step(now) {
                var elapsed = now - startTime;
                var progress = Math.min(elapsed / duration, 1);
                var ease = 0.5 - Math.cos(progress * Math.PI) / 2; // easeInOutQuad

                lon = startLon + (targetLon - startLon) * ease;
                lat = startLat + (targetLat - startLat) * ease;
                if (camera) {
                    camera.fov = startFov + (targetFov - startFov) * ease;
                    camera.updateProjectionMatrix();
                }

                velLon = 0;
                velLat = 0;

                if (progress < 1) {
                    requestAnimationFrame(step);
                }
            }
            requestAnimationFrame(step);
        }

        // Pointer Event Handlers for Dragging on canvasContainer
        function onPointerDown(event) {
            if (!is360Mode) return;
            if (event.target.closest('.video360-controls-bar, .video360-top-bar, .video360-center-play')) {
                return;
            }

            isUserInteracting = true;
            pointerStartX = event.clientX;
            pointerStartY = event.clientY;
            pointerMoved = false;

            lastPointerX = event.clientX;
            lastPointerY = event.clientY;
            onPointerDownLon = lon;
            onPointerDownLat = lat;
            velLon = 0;
            velLat = 0;

            try {
                canvasContainer.setPointerCapture(event.pointerId);
            } catch (e) {}
        }

        function onPointerMove(event) {
            if (!is360Mode || !isUserInteracting) return;

            var dx = event.clientX - lastPointerX;
            var dy = event.clientY - lastPointerY;
            lastPointerX = event.clientX;
            lastPointerY = event.clientY;

            if (Math.abs(event.clientX - pointerStartX) > 5 || Math.abs(event.clientY - pointerStartY) > 5) {
                pointerMoved = true;
                if (hintOverlay) {
                    hintOverlay.style.opacity = '0';
                    setTimeout(function () { if (hintOverlay) hintOverlay.style.display = 'none'; }, 500);
                }
            }

            velLon = -dx * 0.15;
            velLat = dy * 0.15;

            lon += velLon;
            lat += velLat;
        }

        function onPointerUp(event) {
            if (!is360Mode) return;
            isUserInteracting = false;
            try {
                canvasContainer.releasePointerCapture(event.pointerId);
            } catch (e) {}

            // If user simply clicked without dragging, toggle play/pause!
            if (!pointerMoved) {
                togglePlay();
            }
        }

        // Wheel Zooming
        function onWheel(event) {
            if (!is360Mode || !camera) return;
            event.preventDefault();
            var zoomSpeed = 0.05;
            camera.fov = Math.max(30, Math.min(100, camera.fov + event.deltaY * zoomSpeed));
            camera.updateProjectionMatrix();
        }

        // Touch Pinch-to-Zoom
        function onTouchMove(event) {
            if (!is360Mode || !camera || event.touches.length !== 2) return;
            var touch1 = event.touches[0];
            var touch2 = event.touches[1];
            var dist = Math.hypot(touch2.clientX - touch1.clientX, touch2.clientY - touch1.clientY);

            if (initialPinchDistance === null) {
                initialPinchDistance = dist;
                initialFov = camera.fov;
            } else {
                var factor = initialPinchDistance / dist;
                camera.fov = Math.max(30, Math.min(100, initialFov * factor));
                camera.updateProjectionMatrix();
            }
        }

        function onTouchEnd() {
            initialPinchDistance = null;
        }

        // Resize Listener
        function onWindowResize() {
            if (!renderer || !camera || !canvasContainer) return;
            var width = canvasContainer.clientWidth || wrapper.clientWidth;
            var height = canvasContainer.clientHeight || wrapper.clientHeight;
            if (width > 0 && height > 0) {
                camera.aspect = width / height;
                camera.updateProjectionMatrix();
                renderer.setSize(width, height);
            }
        }

        // Toggle 360° Sphere vs Flat 2D
        function setMode(to360) {
            var wasPlaying = !video.paused && !video.ended;
            is360Mode = to360;

            if (is360Mode) {
                flatContainer.style.display = 'none';
                canvasContainer.style.display = 'block';
                btnMode360.classList.add('active');
                btnModeFlat.classList.remove('active');
                badgeText.textContent = '360° Sphere Mode';
                compassBtn.style.display = 'flex';
                btnAutoRotate.style.display = 'inline-flex';
                btnResetView.style.display = 'inline-flex';

                if (hintOverlay) {
                    hintOverlay.style.display = 'flex';
                    hintOverlay.style.opacity = '1';
                    setTimeout(function () {
                        if (hintOverlay) {
                            hintOverlay.style.opacity = '0';
                            setTimeout(function () { if (hintOverlay) hintOverlay.style.display = 'none'; }, 500);
                        }
                    }, 3500);
                }

                if (!renderer) {
                    initThreeJS();
                } else {
                    onWindowResize();
                    if (texture) texture.needsUpdate = true;
                }

                if (wasPlaying) {
                    var p1 = video.play();
                    if (p1 !== undefined) {
                        p1.catch(function (e) { console.warn('[Video360] Mode switch play notice:', e); });
                    }
                }
            } else {
                canvasContainer.style.display = 'none';
                flatContainer.style.display = 'flex';
                btnMode360.classList.remove('active');
                btnModeFlat.classList.add('active');
                badgeText.textContent = 'Standard 2D Mode';
                compassBtn.style.display = 'none';
                btnAutoRotate.style.display = 'none';
                btnResetView.style.display = 'none';

                if (hintOverlay) {
                    hintOverlay.style.display = 'none';
                }

                if (wasPlaying) {
                    var p2 = video.play();
                    if (p2 !== undefined) {
                        p2.catch(function (e) { console.warn('[Video360] Mode switch play notice:', e); });
                    }
                }
            }
        }

        // Play / Pause Toggle
        function togglePlay() {
            if (video.paused || video.ended) {
                var playPromise = video.play();
                if (playPromise !== undefined) {
                    playPromise.then(function () {
                        btnPlay.innerHTML = '<i class="bi bi-pause-fill"></i>';
                        centerPlayBtn.style.display = 'none';
                        showControls();
                    }).catch(function (err) {
                        console.warn('[Video360] Autoplay/Play prevented:', err);
                        btnPlay.innerHTML = '<i class="bi bi-play-fill"></i>';
                        centerPlayBtn.style.display = 'flex';
                    });
                }
            } else {
                video.pause();
                btnPlay.innerHTML = '<i class="bi bi-play-fill"></i>';
                centerPlayBtn.style.display = 'flex';
                showControls();
            }
        }

        // Video Event Listeners
        video.addEventListener('play', function () {
            btnPlay.innerHTML = '<i class="bi bi-pause-fill"></i>';
            centerPlayBtn.style.display = 'none';
        });

        video.addEventListener('pause', function () {
            btnPlay.innerHTML = '<i class="bi bi-play-fill"></i>';
            centerPlayBtn.style.display = 'flex';
        });

        video.addEventListener('timeupdate', function () {
            if (!video.duration) return;
            var pct = (video.currentTime / video.duration) * 100;
            progressPlayed.style.width = pct + '%';
            progressThumb.style.left = pct + '%';
            currentTimeEl.textContent = formatTime(video.currentTime);
        });

        video.addEventListener('durationchange', function () {
            totalDurationEl.textContent = formatTime(video.duration);
        });

        video.addEventListener('progress', function () {
            if (video.buffered.length > 0 && video.duration > 0) {
                var bufferedEnd = video.buffered.end(video.buffered.length - 1);
                var pct = (bufferedEnd / video.duration) * 100;
                progressBuffer.style.width = pct + '%';
            }
        });

        video.addEventListener('volumechange', function () {
            volumeSlider.value = video.muted ? 0 : video.volume;
            if (video.muted || video.volume === 0) {
                btnVolume.innerHTML = '<i class="bi bi-volume-mute-fill text-danger"></i>';
            } else if (video.volume < 0.5) {
                btnVolume.innerHTML = '<i class="bi bi-volume-down-fill"></i>';
            } else {
                btnVolume.innerHTML = '<i class="bi bi-volume-up-fill"></i>';
            }
        });

        video.addEventListener('loadedmetadata', function () {
            totalDurationEl.textContent = formatTime(video.duration);
            if (autoPlay) {
                togglePlay();
            }
        });

        // Scrubber Seeking
        var isSeeking = false;
        function seek(event) {
            var rect = progressContainer.getBoundingClientRect();
            var pos = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
            if (video.duration) {
                video.currentTime = pos * video.duration;
            }
        }

        progressContainer.addEventListener('mousedown', function (e) {
            isSeeking = true;
            seek(e);
        });

        progressContainer.addEventListener('mousemove', function (e) {
            var rect = progressContainer.getBoundingClientRect();
            var pos = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
            if (video.duration) {
                timeTooltip.textContent = formatTime(pos * video.duration);
                timeTooltip.style.left = (pos * 100) + '%';
                timeTooltip.style.display = 'block';
            }
            if (isSeeking) seek(e);
        });

        progressContainer.addEventListener('mouseleave', function () {
            timeTooltip.style.display = 'none';
        });

        document.addEventListener('mouseup', function () {
            isSeeking = false;
        });

        // UI Controls Events - stop propagation to avoid canvas drag interception
        centerPlayBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            e.preventDefault();
            togglePlay();
        });
        centerPlayBtn.addEventListener('pointerdown', function (e) {
            e.stopPropagation();
        });

        btnPlay.addEventListener('click', function (e) {
            e.stopPropagation();
            e.preventDefault();
            togglePlay();
        });
        btnPlay.addEventListener('pointerdown', function (e) {
            e.stopPropagation();
        });

        btnVolume.addEventListener('click', function (e) {
            e.stopPropagation();
            video.muted = !video.muted;
        });

        volumeSlider.addEventListener('input', function (e) {
            e.stopPropagation();
            video.volume = parseFloat(e.target.value);
            video.muted = (video.volume === 0);
        });

        btnMode360.addEventListener('click', function (e) {
            e.stopPropagation();
            setMode(true);
        });
        btnModeFlat.addEventListener('click', function (e) {
            e.stopPropagation();
            setMode(false);
        });

        btnAutoRotate.addEventListener('click', function (e) {
            e.stopPropagation();
            isAutoRotating = !isAutoRotating;
            if (isAutoRotating) {
                btnAutoRotate.classList.add('active');
                btnAutoRotate.querySelector('i').classList.add('video360-spinning');
            } else {
                btnAutoRotate.classList.remove('active');
                btnAutoRotate.querySelector('i').classList.remove('video360-spinning');
            }
        });

        btnResetView.addEventListener('click', function (e) {
            e.stopPropagation();
            resetView();
        });
        compassBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            resetView();
        });

        // Prevent controls bar from triggering canvas drag
        controlsBar.addEventListener('pointerdown', function (e) {
            e.stopPropagation();
        });
        topBar.addEventListener('pointerdown', function (e) {
            e.stopPropagation();
        });

        // Speed Cycle (0.5x -> 1x -> 1.25x -> 1.5x -> 2x)
        var speeds = [0.5, 1, 1.25, 1.5, 2];
        var speedIndex = 1;
        btnSpeed.addEventListener('click', function (e) {
            e.stopPropagation();
            speedIndex = (speedIndex + 1) % speeds.length;
            var spd = speeds[speedIndex];
            video.playbackRate = spd;
            btnSpeed.textContent = spd + 'x';
        });

        // Fullscreen Toggle
        btnFullscreen.addEventListener('click', function (e) {
            e.stopPropagation();
            if (!document.fullscreenElement && !document.webkitFullscreenElement) {
                if (wrapper.requestFullscreen) {
                    wrapper.requestFullscreen();
                } else if (wrapper.webkitRequestFullscreen) {
                    wrapper.webkitRequestFullscreen();
                }
            } else {
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                } else if (document.webkitExitFullscreen) {
                    document.webkitExitFullscreen();
                }
            }
        });

        document.addEventListener('fullscreenchange', function () {
            var isFull = Boolean(document.fullscreenElement || document.webkitFullscreenElement);
            if (isFull) {
                btnFullscreen.innerHTML = '<i class="bi bi-fullscreen-exit"></i>';
            } else {
                btnFullscreen.innerHTML = '<i class="bi bi-arrows-fullscreen"></i>';
            }
            setTimeout(onWindowResize, 150);
        });

        // Keyboard Controls
        wrapper.addEventListener('keydown', function (e) {
            switch (e.key) {
                case ' ':
                case 'k':
                case 'K':
                    e.preventDefault();
                    togglePlay();
                    break;
                case 'f':
                case 'F':
                    e.preventDefault();
                    btnFullscreen.click();
                    break;
                case 'm':
                case 'M':
                    e.preventDefault();
                    video.muted = !video.muted;
                    break;
                case 'r':
                case 'R':
                    e.preventDefault();
                    resetView();
                    break;
                case 'ArrowLeft':
                case 'a':
                case 'A':
                    e.preventDefault();
                    if (is360Mode) lon -= 5;
                    else video.currentTime = Math.max(0, video.currentTime - 5);
                    break;
                case 'ArrowRight':
                case 'd':
                case 'D':
                    e.preventDefault();
                    if (is360Mode) lon += 5;
                    else video.currentTime = Math.min(video.duration, video.currentTime + 5);
                    break;
                case 'ArrowUp':
                case 'w':
                case 'W':
                    e.preventDefault();
                    if (is360Mode) lat += 4;
                    else video.volume = Math.min(1, video.volume + 0.1);
                    break;
                case 'ArrowDown':
                case 's':
                case 'S':
                    e.preventDefault();
                    if (is360Mode) lat -= 4;
                    else video.volume = Math.max(0, video.volume - 0.1);
                    break;
                case '+':
                case '=':
                    e.preventDefault();
                    if (camera) {
                        camera.fov = Math.max(30, camera.fov - 5);
                        camera.updateProjectionMatrix();
                    }
                    break;
                case '-':
                case '_':
                    e.preventDefault();
                    if (camera) {
                        camera.fov = Math.min(100, camera.fov + 5);
                        camera.updateProjectionMatrix();
                    }
                    break;
            }
        });

        // Canvas Interaction Events strictly on canvasContainer
        canvasContainer.addEventListener('pointerdown', onPointerDown);
        canvasContainer.addEventListener('pointermove', onPointerMove);
        canvasContainer.addEventListener('pointerup', onPointerUp);
        canvasContainer.addEventListener('pointercancel', onPointerUp);
        canvasContainer.addEventListener('wheel', onWheel, { passive: false });
        canvasContainer.addEventListener('touchmove', onTouchMove, { passive: false });
        canvasContainer.addEventListener('touchend', onTouchEnd);

        wrapper.addEventListener('mousemove', showControls);
        wrapper.addEventListener('touchstart', showControls, { passive: true });

        window.addEventListener('resize', onWindowResize);

        // Auto-fade hint overlay after 4 seconds
        setTimeout(function () {
            if (hintOverlay) {
                hintOverlay.style.opacity = '0';
                setTimeout(function () { if (hintOverlay) hintOverlay.style.display = 'none'; }, 500);
            }
        }, 4500);

        // Initialize 3D Engine & Mode
        initThreeJS();
        if (!is360Mode) {
            setMode(false);
        }

        // Return controller object with clean lifecycle methods
        var playerInstance = {
            video: video,
            wrapper: wrapper,
            setMode: setMode,
            resetView: resetView,
            togglePlay: togglePlay,
            destroy: function () {
                isDestroyed = true;
                if (animationFrameId) {
                    cancelAnimationFrame(animationFrameId);
                    animationFrameId = null;
                }
                window.removeEventListener('resize', onWindowResize);

                try {
                    video.pause();
                    video.removeAttribute('src');
                    video.load();
                } catch (e) {}

                if (renderer) {
                    try {
                        renderer.dispose();
                        if (renderer.domElement && renderer.domElement.parentNode) {
                            renderer.domElement.parentNode.removeChild(renderer.domElement);
                        }
                    } catch (e) {}
                }

                if (material) material.dispose();
                if (texture) texture.dispose();
                if (geometry) geometry.dispose();

                container.innerHTML = '';
            }
        };

        return playerInstance;
    }

    // Expose Globally
    window.is360Video = is360Video;
    window.init360VideoPlayer = init360VideoPlayer;

})(window, document);
