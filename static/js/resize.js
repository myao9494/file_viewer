document.addEventListener('DOMContentLoaded', function() {
    const sizeInput = document.getElementById('size-input');
    const sizeLabel = document.querySelector('label[for="size-input"]');
    const content = document.getElementById('svg-content') || document.getElementById('image-content');
    const container = document.getElementById('svg-container') || document.getElementById('image-container');

    function updateSize() {
        let size = parseInt(sizeInput.value);
        size = Math.round(size / 2) * 2; // 2の倍数に丸める
        size = Math.min(Math.max(size, 10), 200); // 10%から200%の間に制限
        sizeInput.value = size; // 入力欄の値を更新
        if (content) {
            content.style.width = `${size}%`;
            content.style.height = 'auto';
        }
        if (container) {
            container.style.width = size > 100 ? `${size}%` : '100%';
        }
    }

    function calculateInitialSize() {
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        let contentWidth, contentHeight;

        if (content.tagName.toLowerCase() === 'img') {
            // 画像の場合
            contentWidth = content.naturalWidth;
            contentHeight = content.naturalHeight;
        } else {
            // SVGの場合
            const svgElement = content.querySelector('svg');
            if (svgElement) {
                // SVGの幅と高さを取得
                contentWidth = svgElement.width.baseVal.value;
                contentHeight = svgElement.height.baseVal.value;

                // 幅と高さが設定されていない場合は、viewBoxから取得
                if (contentWidth === 0 || contentHeight === 0) {
                    const viewBox = svgElement.viewBox.baseVal;
                    contentWidth = viewBox.width;
                    contentHeight = viewBox.height;
                }

                // それでも取得できない場合は、SVGの現在のサイズを使用
                if (contentWidth === 0 || contentHeight === 0) {
                    contentWidth = svgElement.getBoundingClientRect().width;
                    contentHeight = svgElement.getBoundingClientRect().height;
                }
            } else {
                // SVG要素が見つからない場合はデフォルト値を使用
                return 35;
            }
        }

        let widthRatio = viewportWidth / contentWidth;
        let heightRatio = viewportHeight / contentHeight;

        // widthRatioとheightRatioが1以下になるように調整
        if (widthRatio > 1 || heightRatio > 1) {
            const maxRatio = Math.max(widthRatio, heightRatio);
            widthRatio /= maxRatio;
            heightRatio /= maxRatio;
        }

        let initialSize = Math.min(widthRatio, heightRatio) * 100;

        initialSize = Math.min(Math.max(initialSize, 15), 100); // 30%から80%の間に制限
        return Math.round(initialSize / 2) * 2; // 2の倍数に丸める
    }

    function handleWheel(event) {
        event.preventDefault(); // デフォルトのスクロール動作を防止
        let delta = event.deltaY || event.detail || event.wheelDelta;
        let currentSize = parseInt(sizeInput.value);
        
        if (delta < 0) {
            // 上方向のジェスチャー（拡大）
            currentSize += 2;
        } else {
            // 下方向のジェスチャー（縮小）
            currentSize -= 2;
        }
        
        sizeInput.value = currentSize;
        updateSize();
    }

    sizeInput.addEventListener('input', updateSize);
    sizeInput.addEventListener('wheel', handleWheel, { passive: false });
    sizeLabel.addEventListener('wheel', handleWheel, { passive: false });

    // コンテナ全体でのホイール操作を無効化
    container.addEventListener('wheel', function(event) {
        // カーソルがサイズ調整領域上にある場合のみイベントを処理
        if (event.target === sizeInput || event.target === sizeLabel) {
            handleWheel(event);
        }
    }, { passive: false });

    // 初期サイズを自動計算して設定
    const initialSize = calculateInitialSize();
    sizeInput.value = initialSize;
    updateSize();
});