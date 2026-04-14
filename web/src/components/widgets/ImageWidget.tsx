import React, {
  ChangeEvent,
  useState,
  useRef,
  useEffect,
  useCallback,
  useMemo,
} from "react";

interface ImageWidgetProps {
  value?: string;
  onChange: (value: string | undefined) => void;
  schema: any;
  uiSchema?: any;
}

const PRINTER_WIDTH = 384; // Constant for the printer width

const ASPECT_RATIOS = [
  { label: "Original", value: "original" },
  { label: "Square (1:1)", value: "1:1" },
  { label: "Landscape (4:3)", value: "4:3" },
  { label: "Portrait (3:4)", value: "3:4" },
  { label: "Widescreen (16:9)", value: "16:9" },
  { label: "Tall (9:16)", value: "9:16" },
];

const ASPECT_RATIO_VALUES: Record<string, number | null> = {
  "1:1": 1,
  "4:3": 4 / 3,
  "3:4": 3 / 4,
  "16:9": 16 / 9,
  "9:16": 9 / 16,
  original: null,
};
const ImageWidget: React.FC<ImageWidgetProps> = ({
  value,
  onChange,
  uiSchema,
}) => {
  const options = uiSchema?.["ui:options"] || {};
  const accept = options.accept || "image/*";

  const [editSrc, setEditSrc] = useState<string | undefined>(undefined);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [rotation, setRotation] = useState(0);
  const [displayScale, setDisplayScale] = useState(1);
  const [selectedAspectRatio, setSelectedAspectRatio] = useState<string>("original");
  const [imageNaturalDimensions, setImageNaturalDimensions] = useState<{
    width: number | null;
    height: number | null;
  }>({ width: null, height: null });

  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  // Memoize the height the image would have if its width was PRINTER_WIDTH
  const scaledImageHeight = useMemo(() => {
    if (imageNaturalDimensions.width && imageNaturalDimensions.height) {
      return PRINTER_WIDTH * (imageNaturalDimensions.height / imageNaturalDimensions.width);
    }
    return 0;
  }, [imageNaturalDimensions]);

  // Memoize the height of the preview container based on aspect ratio
  const currentPreviewHeight = useMemo(() => {
    const aspectRatioVal = ASPECT_RATIO_VALUES[selectedAspectRatio];
    if (aspectRatioVal !== null) {
      return PRINTER_WIDTH / aspectRatioVal;
    }
    return scaledImageHeight || 256;
  }, [selectedAspectRatio, scaledImageHeight]);

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      onChange(undefined);
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const result = e.target?.result;
      if (typeof result === "string") {
        setEditSrc(result);
        setZoom(1);
        setOffset({ x: 0, y: 0 });
        setRotation(0);
        setSelectedAspectRatio("original"); // Reset aspect ratio on new image load
        setImageNaturalDimensions({ width: null, height: null }); // Reset natural dimensions until image loads
      }
    };
    reader.readAsDataURL(file);
  };

  const handleImageLoad = () => {
    if (imgRef.current) {
      setImageNaturalDimensions({
        width: imgRef.current.naturalWidth,
        height: imgRef.current.naturalHeight,
      });
    }
  };

  const handleStart = (e: React.MouseEvent | React.TouchEvent) => {
    if (!editSrc) return;
    // Prevent browser from trying to drag the image ghost or select text
    if (e.cancelable) e.preventDefault();

    setIsDragging(true);
    const clientX =
      "touches" in e ? e.touches[0].clientX : (e as React.MouseEvent).clientX;
    const clientY =
      "touches" in e ? e.touches[0].clientY : (e as React.MouseEvent).clientY;
    setDragStart({
      x: clientX - offset.x * displayScale,
      y: clientY - offset.y * displayScale,
    });
  };

  useEffect(() => {
    const handleGlobalMove = (e: MouseEvent | TouchEvent) => {
      if (!isDragging) return;
      const isTouch = "touches" in e;
      if (isTouch && e.cancelable) e.preventDefault();
      const clientX = isTouch
        ? (e as TouchEvent).touches[0].clientX
        : (e as MouseEvent).clientX;
      const clientY = isTouch
        ? (e as TouchEvent).touches[0].clientY
        : (e as MouseEvent).clientY;
      setOffset({
        x: (clientX - dragStart.x) / displayScale,
        y: (clientY - dragStart.y) / displayScale,
      });
    };
    const handleGlobalUp = () => setIsDragging(false);

    if (isDragging) {
      window.addEventListener("mousemove", handleGlobalMove);
      window.addEventListener("mouseup", handleGlobalUp);
      window.addEventListener("touchmove", handleGlobalMove, {
        passive: false,
      });
      window.addEventListener("touchend", handleGlobalUp);
    }
    return () => {
      window.removeEventListener("mousemove", handleGlobalMove);
      window.removeEventListener("mouseup", handleGlobalUp);
      window.removeEventListener("touchmove", handleGlobalMove);
      window.removeEventListener("touchend", handleGlobalUp);
    };
  }, [isDragging, dragStart, displayScale]); 

  // Handle responsive scaling and prevent background scroll
  useEffect(() => {
    // Effect for responsive scaling and touch event prevention
    const handleResize = () => {
      if (containerRef.current?.parentElement) {
        const availableWidth = containerRef.current.parentElement.offsetWidth;
        const scale = Math.min(1, availableWidth / PRINTER_WIDTH);
        setDisplayScale(scale);
      }
    };

    const container = containerRef.current;
    const preventDefault = (e: TouchEvent) => {
      if (e.cancelable) e.preventDefault();
    };

    if (editSrc && container) {
      // Only set up listeners if editor is active
      handleResize();
      window.addEventListener("resize", handleResize);
      container.addEventListener("touchstart", preventDefault as any, {
        passive: false,
      });
      return () => {
        window.removeEventListener("resize", handleResize);
        container.removeEventListener("touchstart", preventDefault as any);
      };
    }
  }, [editSrc, currentPreviewHeight]);

  const saveEditedImage = useCallback(() => {
    if (
      !imgRef.current ||
      !imageNaturalDimensions.width ||
      !imageNaturalDimensions.height
    )
      return;

    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = PRINTER_WIDTH;
    canvas.height = currentPreviewHeight;

    ctx.fillStyle = "white";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.save();
    ctx.translate(offset.x + PRINTER_WIDTH / 2, offset.y + scaledImageHeight / 2);
    ctx.rotate((rotation * Math.PI) / 180);
    ctx.scale(zoom, zoom);
    ctx.drawImage(
      imgRef.current,
      -PRINTER_WIDTH / 2,
      -scaledImageHeight / 2,
      PRINTER_WIDTH,
      scaledImageHeight,
    );
    ctx.restore();

    onChange(canvas.toDataURL("image/png")); // Save the image data URL
  }, [
    scaledImageHeight,
    currentPreviewHeight,
    offset.x,
    offset.y,
    rotation,
    zoom,
    onChange,
  ]);

  // Effect to automatically save the image whenever relevant editing states change
  useEffect(() => {
    // Only save if an image is being edited and its natural dimensions are known
    // and the image has actually loaded in the editor (imgRef.current is available)
    if (
      editSrc &&
      imgRef.current &&
      imageNaturalDimensions.width &&
      imageNaturalDimensions.height
    ) {
      // Debounce the save operation to avoid excessive calls during rapid changes (e.g., dragging, zooming)
      const handler = setTimeout(() => {
        saveEditedImage();
      }, 300); // Debounce for 300ms

      return () => {
        clearTimeout(handler);
      };
    }
  }, [
    editSrc,
    zoom,
    offset,
    rotation,
    selectedAspectRatio,
    imageNaturalDimensions.width,
    imageNaturalDimensions.height,
    currentPreviewHeight,
    saveEditedImage,
  ]);

  return (
    <div className="space-y-2">
      <input
        type="file"
        accept={accept}
        onChange={handleChange}
        className="block w-full text-sm text-slate-500
          file:mr-4 file:py-2 file:px-4
          file:rounded-md file:border-0
          file:text-sm file:font-semibold
          file:bg-slate-100 file:text-slate-700
          hover:file:bg-slate-200 cursor-pointer"
      />
      {editSrc && (
        <div className="space-y-3 p-3 border rounded-lg bg-slate-50 border-slate-200 shadow-sm">
          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            Adjust Print Preview
          </div>
          <div
            className="mx-auto border border-slate-300 rounded overflow-hidden bg-white shadow-inner"
            style={{
              maxWidth: PRINTER_WIDTH * displayScale,
              height: currentPreviewHeight * displayScale,
            }}
          >
            <div
              ref={containerRef}
              className="relative cursor-move select-none"
              style={{
                width: PRINTER_WIDTH,
                height: currentPreviewHeight,
                touchAction: "none",
                transform: `scale(${displayScale})`,
                transformOrigin: "top left",
              }}
              onMouseDown={handleStart}
              onTouchStart={handleStart}
              onDragStart={(e) => e.preventDefault()}
            >
              <img
                ref={imgRef}
                src={editSrc}
                alt="Editor"
                draggable={false}
                className="absolute pointer-events-none"
                style={{
                  transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom}) rotate(${rotation}deg)`,
                  transformOrigin: "center",
                  // The image should be initially sized to fit the PRINTER_WIDTH,
                  // then scaled by zoom.
                  width: PRINTER_WIDTH,
                  height: "auto", // Use natural height
                  filter: "grayscale(1) contrast(2) brightness(1.1)",
                  imageRendering: "pixelated",
                }}
                onLoad={handleImageLoad} // Call onLoad to get natural dimensions
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-400 font-mono">ZOOM</span>
            <input
              type="range"
              min="0.1"
              max="5"
              step="0.01"
              value={zoom}
              onChange={(e) => setZoom(parseFloat(e.target.value))}
              className="flex-1 accent-black h-2.5 bg-slate-200 rounded-lg appearance-none cursor-pointer border border-slate-300 shadow-sm"
            />
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-400 font-mono">ROTATE</span>
            <button
              type="button"
              onClick={() => {
                setRotation((r) => (r + 90) % 360);
                // Automatically center the image in the view upon rotation
                if (scaledImageHeight) {
                  setOffset({
                    x: 0,
                    y: (currentPreviewHeight - scaledImageHeight) / 2,
                  });
                }
              }}
              className="flex-1 py-1 border rounded-md text-sm bg-white border-slate-300 shadow-sm hover:bg-slate-50 transition-colors"
            >
              Rotate 90°
            </button>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-400 font-mono">
              ASPECT RATIO
            </span>
            <select
              value={selectedAspectRatio}
              onChange={(e) => setSelectedAspectRatio(e.target.value)}
              className="flex-1 p-1 border rounded-md text-sm bg-white border-slate-300 shadow-sm"
            >
              {ASPECT_RATIOS.map((ratio) => (
                <option key={ratio.value} value={ratio.value}>
                  {ratio.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {value && value.startsWith("data:") && !editSrc && (
        <div className="relative inline-block border rounded-md overflow-hidden bg-white shadow-inner group">
          {value.startsWith("data:image") ? (
            <img
              src={value}
              alt="Upload Preview"
              className="h-auto object-contain"
            />
          ) : (
            <div className="p-2 text-xs text-slate-500">File attached</div>
          )}
          <button
            type="button"
            onClick={() => onChange(undefined)}
            className="absolute top-0 right-0 bg-red-500 text-white p-1 leading-none rounded-bl hover:bg-red-600 transition-colors"
            title="Remove file"
          >
            &times;
          </button>
        </div>
      )}
    </div>
  );
};

export default ImageWidget;
