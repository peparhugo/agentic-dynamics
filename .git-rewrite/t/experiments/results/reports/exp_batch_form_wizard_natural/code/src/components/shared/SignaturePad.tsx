import { useRef, useState, useCallback, useEffect, useId } from 'react';
import type { SignatureData } from '../../types';

interface SignaturePadProps {
  label: string;
  value: SignatureData | null;
  onChange: (signature: SignatureData) => void;
  error?: string;
  required?: boolean;
  disabled?: boolean;
}

export function SignaturePad({
  label,
  value,
  onChange,
  error,
  required = false,
  disabled = false,
}: SignaturePadProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [hasSignature, setHasSignature] = useState(!!value?.dataUrl);
  const id = useId();
  const errorId = `${id}-error`;

  const getCanvasContext = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    return canvas.getContext('2d');
  }, []);

  const startDrawing = useCallback(
    (e: React.MouseEvent | React.TouchEvent | React.PointerEvent) => {
      if (disabled) return;
      const ctx = getCanvasContext();
      if (!ctx) return;

      const canvas = canvasRef.current!;
      const rect = canvas.getBoundingClientRect();
      let clientX: number, clientY: number;

      if ('touches' in e) {
        const touch = e.touches[0] || (e as React.TouchEvent).changedTouches[0];
        clientX = touch.clientX;
        clientY = touch.clientY;
      } else {
        clientX = (e as React.MouseEvent).clientX;
        clientY = (e as React.MouseEvent).clientY;
      }

      ctx.beginPath();
      ctx.moveTo(clientX - rect.left, clientY - rect.top);
      setIsDrawing(true);
    },
    [disabled, getCanvasContext]
  );

  const draw = useCallback(
    (e: React.MouseEvent | React.TouchEvent | React.PointerEvent) => {
      if (!isDrawing || disabled) return;
      const ctx = getCanvasContext();
      if (!ctx) return;

      const canvas = canvasRef.current!;
      const rect = canvas.getBoundingClientRect();
      let clientX: number, clientY: number;

      if ('touches' in e) {
        const touch = e.touches[0] || (e as React.TouchEvent).changedTouches[0];
        clientX = touch.clientX;
        clientY = touch.clientY;
      } else {
        clientX = (e as React.MouseEvent).clientX;
        clientY = (e as React.MouseEvent).clientY;
      }

      ctx.lineWidth = 2;
      ctx.lineCap = 'round';
      ctx.strokeStyle = '#000';
      ctx.lineTo(clientX - rect.left, clientY - rect.top);
      ctx.stroke();
    },
    [isDrawing, disabled, getCanvasContext]
  );

  const stopDrawing = useCallback(() => {
    if (!isDrawing) return;
    setIsDrawing(false);
    setHasSignature(true);

    const canvas = canvasRef.current;
    if (canvas && !canvas.toDataURL().includes('data:,')) {
      onChange({
        dataUrl: canvas.toDataURL(),
        signedAt: new Date().toISOString(),
      });
    }
  }, [isDrawing, onChange]);

  const clearSignature = useCallback(() => {
    const ctx = getCanvasContext();
    const canvas = canvasRef.current;
    if (ctx && canvas) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    setHasSignature(false);
    onChange({ dataUrl: '', signedAt: new Date().toISOString() });
  }, [getCanvasContext, onChange]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (disabled) return;
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        if (hasSignature) {
          clearSignature();
        } else {
          // Simulate a simple signature for keyboard-only users
          const ctx = getCanvasContext();
          const canvas = canvasRef.current;
          if (ctx && canvas) {
            ctx.strokeStyle = '#000';
            ctx.lineWidth = 2;
            ctx.lineCap = 'round';
            ctx.beginPath();
            ctx.moveTo(20, canvas.height / 2);
            ctx.quadraticCurveTo(canvas.width / 2, 10, canvas.width - 20, canvas.height / 2);
            ctx.stroke();
            setHasSignature(true);
            onChange({
              dataUrl: canvas.toDataURL(),
              signedAt: new Date().toISOString(),
            });
          }
        }
      }
    },
    [disabled, hasSignature, clearSignature, getCanvasContext, onChange]
  );

  // Set canvas size
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (parent) {
      canvas.width = parent.clientWidth - 4;
      canvas.height = 150;
    }
  }, []);

  // Restore existing signature
  useEffect(() => {
    if (value?.dataUrl && canvasRef.current) {
      const img = new Image();
      img.onload = () => {
        const ctx = getCanvasContext();
        if (ctx) {
          ctx.drawImage(img, 0, 0);
          setHasSignature(true);
        }
      };
      img.src = value.dataUrl;
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="form-field" role="group">
      <label className="form-label">
        {label}
        {required && <span className="required-asterisk" aria-hidden="true"> *</span>}
      </label>
      <div
        className={`signature-pad${error ? ' signature-pad--error' : ''}`}
        style={{
          border: `2px solid ${error ? '#dc3545' : '#ccc'}`,
          borderRadius: '4px',
          position: 'relative',
          touchAction: 'none',
        }}
      >
        <canvas
          ref={canvasRef}
          id={id}
          style={{
            display: 'block',
            width: '100%',
            height: '150px',
            cursor: disabled ? 'not-allowed' : 'crosshair',
          }}
          onPointerDown={startDrawing}
          onPointerMove={draw}
          onPointerUp={stopDrawing}
          onPointerLeave={stopDrawing}
          onTouchStart={startDrawing}
          onTouchMove={draw}
          onTouchEnd={stopDrawing}
          role="img"
          aria-label={`Signature pad for ${label}. Press Enter or Space to toggle signature.`}
          tabIndex={0}
          onKeyDown={handleKeyDown}
          aria-required={required}
        />
        {hasSignature && !disabled && (
          <button
            type="button"
            onClick={clearSignature}
            className="btn btn--danger btn--small signature-clear-btn"
            aria-label="Clear signature"
          >
            Clear
          </button>
        )}
      </div>
      {error && (
        <p id={errorId} className="form-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
