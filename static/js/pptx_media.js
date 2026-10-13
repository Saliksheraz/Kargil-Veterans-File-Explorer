/* Shared embedded video and panorama photo support for PowerPoint previews. */
(function (window, document) {
    'use strict';

    function escapeAttribute(value) {
        return String(value || '').replace(/[&<>"']/g, function (ch) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
        });
    }

    function mount(container, media) {
        container.classList.add('pptx-media-host');
        var player = media.kind === 'image' ? window.init360ImageViewer(container, media.url, {
            title: media.title || media.name || '', is360Default: true, embedded: true
        }) : window.init360VideoPlayer(container, media.url, {
            title: media.title || media.name || '',
            is360Default: window.is360Video(media.name) || window.is360Video(media.title),
            autoDetect360: true,
            autoPlay: false,
            embedded: true
        });
        container.pptxPlayer = player;
        return player;
    }

    function init(root) {
        root.querySelectorAll('[data-pptx-video-url]').forEach(function (host) {
            if (!host.pptxPlayer) {
                mount(host, { url: host.dataset.pptxVideoUrl, name: host.dataset.pptxVideoName });
            }
        });
        root.querySelectorAll('[data-pptx-image-url]').forEach(function (host) {
            if (!host.pptxPlayer) mount(host, { url: host.dataset.pptxImageUrl, name: host.dataset.pptxImageName, kind: 'image' });
        });
    }

    function destroy(root) {
        if (!root) return;
        root.querySelectorAll('.pptx-media-host').forEach(function (host) {
            if (host.pptxPlayer) {
                host.pptxPlayer.destroy();
                host.pptxPlayer = null;
            }
        });
    }

    function release(root) {
        if (!root) return;
        root.pptxMediaGeneration = (root.pptxMediaGeneration || 0) + 1;
        destroy(root);
        (root.pptxBlobUrls || []).forEach(function (url) { URL.revokeObjectURL(url); });
        root.pptxBlobUrls = [];
    }

    function markup(videos, overlay) {
        return videos.map(function (video) {
            var kind = video.kind === 'image' ? 'image' : 'video';
            var style = overlay ? 'position:absolute;left:' + video.left_pct + '%;top:' + video.top_pct +
                '%;width:' + video.width_pct + '%;height:' + video.height_pct + '%;z-index:25;' :
                'position:relative;width:100%;height:360px;margin:12px auto;max-width:640px;';
            return '<div class="pptx-video-container" style="' + style + '">' +
                '<div class="pptx-video-inner-box" style="transform:rotate(' + video.rotation + 'deg)">' +
                '<div class="pptx-media-host" data-pptx-' + kind + '-url="' + escapeAttribute(video.url) +
                '" data-pptx-' + kind + '-name="' + escapeAttribute(video.name + ' ' + video.title) + '"></div></div></div>';
        }).join('');
    }

    // Read media relationships in the browser fallback, including clips renamed
    // by PowerPoint and duplicate video/media relationships for the same clip.
    async function extract(zip, slide, relsText, root, slideW, slideH, mediaKind) {
        mediaKind = mediaKind || 'video';
        var generation = root.pptxMediaGeneration || 0;
        var rels = {};
        var relDoc = new DOMParser().parseFromString(relsText || '<Relationships/>', 'text/xml');
        Array.from(relDoc.getElementsByTagName('*')).forEach(function (rel) {
            var target = rel.getAttribute('Target') || '';
            var type = rel.getAttribute('Type') || '';
            if (mediaKind === 'image' ? /\.(jpg|jpeg|png|webp|bmp)$/i.test(target) :
                    /\.(mp4|webm|ogv|mov|m4v|avi|wmv|mkv|mpg|mpeg|3gp)(\?.*)?$/i.test(target) || /\/(video|media)$/.test(type)) {
                rels[rel.getAttribute('Id')] = target;
            }
        });
        var shapes = Array.from(slide.getElementsByTagName('*')).filter(function (el) {
            return ['pic', 'sp', 'graphicFrame', 'bg'].includes(el.localName);
        });
        var descriptors = [];
        shapes.forEach(function (shape) {
            if (mediaKind === 'image' && Array.from(shape.getElementsByTagName('*')).some(function (el) {
                return ['videoFile', 'media', 'quickTimeFile'].includes(el.localName);
            })) return;
            var targets = new Set();
            Array.from(shape.getElementsByTagName('*')).forEach(function (el) {
                Array.from(el.attributes).forEach(function (attr) {
                    if (['link', 'embed', 'id'].includes(attr.localName) && rels[attr.value]) targets.add(rels[attr.value]);
                });
            });
            var nodes = Array.from(shape.getElementsByTagName('*'));
            var props = nodes.find(function (el) { return el.localName === 'cNvPr'; });
            var xfrm = nodes.find(function (el) { return el.localName === 'xfrm'; });
            var off = xfrm && Array.from(xfrm.children).find(function (el) { return el.localName === 'off'; });
            var ext = xfrm && Array.from(xfrm.children).find(function (el) { return el.localName === 'ext'; });
            var background = shape.localName === 'bg';
            targets.forEach(function (target) {
                descriptors.push({ target: target, title: props ? [props.getAttribute('name'), props.getAttribute('descr'), props.getAttribute('title')].filter(Boolean).join(' ') : '',
                    left_pct: off ? Number(off.getAttribute('x')) / slideW * 100 : background ? 0 : 10,
                    top_pct: off ? Number(off.getAttribute('y')) / slideH * 100 : background ? 0 : 15,
                    width_pct: ext ? Number(ext.getAttribute('cx')) / slideW * 100 : background ? 100 : 80,
                    height_pct: ext ? Number(ext.getAttribute('cy')) / slideH * 100 : background ? 100 : 70,
                    rotation: xfrm ? Number(xfrm.getAttribute('rot') || 0) / 60000 : 0 });
            });
        });
        if (!descriptors.length && mediaKind === 'video') {
            Array.from(new Set(Object.values(rels))).forEach(function (target) {
                descriptors.push({ target: target, title: '', left_pct: 10, top_pct: 15, width_pct: 80, height_pct: 70, rotation: 0 });
            });
        }
        var urls = {};
        var videos = [];
        for (var media of descriptors) {
            media.kind = mediaKind;
            media.name = media.target.split('/').pop();
            if (/^https?:\/\//i.test(media.target)) {
                media.url = media.target;
            } else {
                var path = media.target.replace(/^\.\.\//, 'ppt/').replace(/^\//, '');
                var file = zip.file(path);
                if (!file) continue;
                if (!urls[path]) {
                    var extension = path.split('.').pop().toLowerCase();
                    var mime = { mp4: 'video/mp4', m4v: 'video/mp4', webm: 'video/webm', ogv: 'video/ogg', mov: 'video/quicktime',
                        jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', webp: 'image/webp', bmp: 'image/bmp' }[extension] || 'application/octet-stream';
                    var data = await file.async('uint8array');
                    if ((root.pptxMediaGeneration || 0) !== generation) return [];
                    urls[path] = URL.createObjectURL(new Blob([data], { type: mime }));
                    (root.pptxBlobUrls || (root.pptxBlobUrls = [])).push(urls[path]);
                }
                media.url = urls[path];
            }
            if (mediaKind === 'image') {
                var namedPanorama = /(360|vr360|360vr|_vr|\bvr\b|equirectangular|panoramic|spherical|panorama|photosphere|pano)/i.test(media.name + ' ' + media.title);
                var ratioPanorama = false;
                if (!namedPanorama) {
                    ratioPanorama = await new Promise(function (resolve) {
                        var image = new Image();
                        image.onload = function () { resolve(image.naturalHeight > 0 && Math.abs(image.naturalWidth / image.naturalHeight - 2) < 0.05); };
                        image.onerror = function () { resolve(false); };
                        image.src = media.url;
                    });
                }
                if (!namedPanorama && !ratioPanorama) continue;
                if ((root.pptxMediaGeneration || 0) !== generation) return [];
            }
            videos.push(media);
        }
        return videos;
    }

    window.PptxMedia = { mount: mount, init: init, destroy: destroy, release: release, markup: markup, extract: extract };
})(window, document);
