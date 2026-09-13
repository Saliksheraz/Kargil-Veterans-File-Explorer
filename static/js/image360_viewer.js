/**
 * 360 Degree Panoramic Image (Photosphere) Viewer for Kargil Veterans File Explorer
 * Uses Three.js for interactive equirectangular spherical WebGL projection.
 * Supports touch drag, mouse drag, inertia, zooming, auto-rotation, compass heading,
 * and seamless 360/Flat 2D mode toggling.
 */

(function (window, document) {
    'use strict';

    // Helper: Detect if a filename represents a 360-degree / VR image
    function is360Image(filename) {
        if (!filename) return false;
        var name = filename.toLowerCase();
        var isImg = Boolean(name.match(/\.(jpg|jpeg|png|webp|bmp)$/i));
        if (!isImg) return false;
        return Boolean(name.match(/(360|360photo|360image|vr360|360vr|_vr|\bvr\b|equirectangular|panoramic|spherical|panorama|photosphere|pano)/i));
    }

    // Main 360 Image Viewer Factory
    function init360ImageViewer(container, imageUrl, options) {
        options = options || {};
        var title = options.title || 'Image Viewer';
        var is360Mode = (typeof options.is360Default === 'boolean') ? options.is360Default : is360Image(title);

        // Ensure container is clean
        container.innerHTML = '';

        // Build Viewer HTML structure
        var wrapper = document.createElement('div');
        wrapper.className = 'image360-wrapper';
        wrapper.tabIndex = 0; // for keyboard focus

        wrapper.innerHTML = [
            '<div class="image360-canvas-container"></div>',
            '<div class="image360-flat-container" style="display: none;">',
            '    <img src="' + imageUrl + '" alt="' + title + '">',
            '</div>',
            '<div class="image360-loading">',
            '    <div class="spinner-border text-warning" role="status"></div>',
            '    <span>Loading 360° Panorama...</span>',
            '</div>',
            '<div class="image360-top-bar">',
            '    <div class="image360-badge-group">',
            '        <span class="image360-badge mode-badge">',
            '            <i class="bi bi-badge-vr-fill"></i> <span class="badge-text">' + (is360Mode ? '360° Sphere Mode' : 'Standard 2D Photo') + '</span>',
            '        </span>',
            '        <button type="button" class="image360-compass-btn" title="Click to Reset View to Center (0° N)">',
            '            <i class="bi bi-compass-fill image360-compass-icon text-warning"></i>',
            '            <span class="compass-text">0° N</span>',
            '        </button>',
            '    </div>',
            '</div>',
            '<div class="image360-hint-overlay">',
            '    <i class="bi bi-arrows-move text-warning fs-5"></i>',
            '    <span>Drag to look 360° &bull; Scroll / Pinch to zoom</span>',
            '</div>',
            '<div class="image360-controls-bar">',
            '    <div class="image360-buttons-left">',
            '        <div class="image360-mode-toggle" title="Switch Projection Mode">',
            '            <button type="button" class="image360-mode-btn btn-mode-360 ' + (is360Mode ? 'active' : '') + '">',
            '                <i class="bi bi-badge-vr"></i> 360°',
            '            </button>',
            '            <button type="button" class="image360-mode-btn btn-mode-flat ' + (!is360Mode ? 'active' : '') + '">',
            '                <i class="bi bi-image"></i> Flat',
            '            </button>',
            '        </div>',
            '        <button type="button" class="image360-btn btn-reset-view" title="Reset View to Front (R)">',
            '            <i class="bi bi-crosshair"></i>',
            '        </button>',
            '        <button type="button" class="image360-btn btn-auto-rotate" title="Toggle Auto-Rotation">',
            '            <i class="bi bi-arrow-repeat"></i>',
            '        </button>',
            '    </div>',
            '    <div class="image360-buttons-right">',
            '        <button type="button" class="image360-btn btn-zoom-in" title="Zoom In (+)">',
            '            <i class="bi bi-plus-lg"></i>',
            '        </button>',
            '        <button type="button" class="image360-btn btn-zoom-out" title="Zoom Out (-)">',
            '            <i class="bi bi-dash-lg"></i>',
            '        </button>',
            '        <button type="button" class="image360-btn btn-fullscreen" title="Fullscreen (F)">',
            '            <i class="bi bi-arrows-fullscreen"></i>',
            '        </button>',
            '    </div>',
            '</div>'
        ].join('\n');

        container.appendChild(wrapper);

        // Elements
        var canvasContainer = wrapper.querySelector('.image360-canvas-container');
        var flatContainer = wrapper.querySelector('.image360-flat-container');
        var flatImg = flatContainer.querySelector('img');
        var loadingEl = wrapper.querySelector('.image360-loading');
        var topBar = wrapper.querySelector('.image360-top-bar');
        var badgeText = wrapper.querySelector('.badge-text');
        var compassBtn = wrapper.querySelector('.image360-compass-btn');
        var compassIcon = wrapper.querySelector('.image360-compass-icon');
        var compassText = wrapper.querySelector('.compass-text');
        var hintOverlay = wrapper.querySelector('.image360-hint-overlay');
        var controlsBar = wrapper.querySelector('.image360-controls-bar');
        var btnMode360 = wrapper.querySelector('.btn-mode-360');
        var btnModeFlat = wrapper.querySelector('.btn-mode-flat');
        var btnResetView = wrapper.querySelector('.btn-reset-view');
        var btnAutoRotate = wrapper.querySelector('.btn-auto-rotate');
        var btnZoomIn = wrapper.querySelector('.btn-zoom-in');
        var btnZoomOut = wrapper.querySelector('.btn-zoom-out');
        var btnFullscreen = wrapper.querySelector('.btn-fullscreen');

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
            controlsBar.classList.remove('image360-controls-hidden');
            topBar.style.opacity = '1';
            clearTimeout(controlsTimeout);
            controlsTimeout = setTimeout(function () {
                controlsBar.classList.add('image360-controls-hidden');
                topBar.style.opacity = '0';
            }, 4000);
        }

        // Initialize Three.js WebGL Scene
        function initThreeJS() {
            if (!window.THREE) {
                console.error('[Image360] Three.js library missing! Falling back to 2D.');
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

            // Inverted Equirectangular Sphere
            geometry = new THREE.SphereGeometry(500, 60, 40);
            geometry.scale(-1, 1, 1);

            var loader = new THREE.TextureLoader();
            loader.load(
                imageUrl,
                function (loadedTexture) {
                    if (isDestroyed) return;
                    texture = loadedTexture;
                    texture.minFilter = THREE.LinearFilter;
                    texture.magFilter = THREE.LinearFilter;

                    material = new THREE.MeshBasicMaterial({ map: texture });
                    mesh = new THREE.Mesh(geometry, material);
                    scene.add(mesh);

                    if (loadingEl) loadingEl.style.display = 'none';

                    // Auto-detect 2:1 aspect ratio equirectangular panoramas
                    if (loadedTexture.image) {
                        var imgRatio = loadedTexture.image.width / loadedTexture.image.height;
                        if (imgRatio >= 1.8 && imgRatio <= 2.2 && options.is360Default === undefined) {
                            setMode(true);
                        }
                    }

                    onWindowResize();
                },
                undefined,
                function (err) {
                    console.error('[Image360] Error loading image texture:', err);
                    if (loadingEl) loadingEl.style.display = 'none';
                    setMode(false);
                }
            );

            // Start animation loop
            animate();
        }

        function animate() {
            if (isDestroyed) return;
            animationFrameId = requestAnimationFrame(animate);

            if (!is360Mode) return;

            // Inertia / Damping / Auto-Rotation
            if (!isUserInteracting) {
                if (isAutoRotating) {
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

            // Clamp latitude
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

        // Pointer Event Handlers strictly on canvasContainer
        function onPointerDown(event) {
            if (!is360Mode) return;
            if (event.target.closest('.image360-controls-bar, .image360-top-bar')) {
                return;
            }

            isUserInteracting = true;
            pointerStartX = event.clientX;
            pointerStartY = event.clientY;

            lastPointerX = event.clientX;
            lastPointerY = event.clientY;
            onPointerDownLon = lon;
            onPointerDownLat = lat;
            velLon = 0;
            velLat = 0;

            if (hintOverlay) {
                hintOverlay.style.opacity = '0';
                setTimeout(function () { if (hintOverlay) hintOverlay.style.display = 'none'; }, 500);
            }

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
                btnZoomIn.style.display = 'inline-flex';
                btnZoomOut.style.display = 'inline-flex';

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
                }
            } else {
                canvasContainer.style.display = 'none';
                flatContainer.style.display = 'flex';
                btnMode360.classList.remove('active');
                btnModeFlat.classList.add('active');
                badgeText.textContent = 'Standard 2D Photo';
                compassBtn.style.display = 'none';
                btnAutoRotate.style.display = 'none';
                btnResetView.style.display = 'none';
                btnZoomIn.style.display = 'none';
                btnZoomOut.style.display = 'none';

                if (hintOverlay) {
                    hintOverlay.style.display = 'none';
                }
            }
        }

        // Button Listeners
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
                btnAutoRotate.querySelector('i').classList.add('image360-spinning');
            } else {
                btnAutoRotate.classList.remove('active');
                btnAutoRotate.querySelector('i').classList.remove('image360-spinning');
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

        btnZoomIn.addEventListener('click', function (e) {
            e.stopPropagation();
            if (camera) {
                camera.fov = Math.max(30, camera.fov - 10);
                camera.updateProjectionMatrix();
            }
        });

        btnZoomOut.addEventListener('click', function (e) {
            e.stopPropagation();
            if (camera) {
                camera.fov = Math.min(100, camera.fov + 10);
                camera.updateProjectionMatrix();
            }
        });

        // Prevent controls bar from triggering canvas drag
        controlsBar.addEventListener('pointerdown', function (e) {
            e.stopPropagation();
        });
        topBar.addEventListener('pointerdown', function (e) {
            e.stopPropagation();
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
                case 'f':
                case 'F':
                    e.preventDefault();
                    btnFullscreen.click();
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
                    break;
                case 'ArrowRight':
                case 'd':
                case 'D':
                    e.preventDefault();
                    if (is360Mode) lon += 5;
                    break;
                case 'ArrowUp':
                case 'w':
                case 'W':
                    e.preventDefault();
                    if (is360Mode) lat += 4;
                    break;
                case 'ArrowDown':
                case 's':
                case 'S':
                    e.preventDefault();
                    if (is360Mode) lat -= 4;
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

        // Auto-fade hint overlay after 4.5 seconds
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
        var viewerInstance = {
            wrapper: wrapper,
            setMode: setMode,
            resetView: resetView,
            destroy: function () {
                isDestroyed = true;
                if (animationFrameId) {
                    cancelAnimationFrame(animationFrameId);
                    animationFrameId = null;
                }
                window.removeEventListener('resize', onWindowResize);

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

        return viewerInstance;
    }

    // Expose Globally
    window.is360Image = is360Image;
    window.init360ImageViewer = init360ImageViewer;

})(window, document);
