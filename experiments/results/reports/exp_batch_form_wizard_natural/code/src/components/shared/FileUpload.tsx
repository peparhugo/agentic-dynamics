import { useId, useRef, useState } from 'react';
import type { UploadedFile } from '../../types';

interface FileUploadProps {
  label: string;
  files: UploadedFile[];
  onAddFile: (file: UploadedFile) => void;
  onRemoveFile: (fileId: string) => void;
  error?: string;
  accept?: string;
  maxFiles?: number;
  maxSizeMB?: number;
  disabled?: boolean;
}

function fileToUploaded(file: File): Promise<UploadedFile> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      resolve({
        id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        name: file.name,
        size: file.size,
        type: file.type,
        dataUrl: reader.result as string,
      });
    };
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsDataURL(file);
  });
}

export function FileUpload({
  label,
  files,
  onAddFile,
  onRemoveFile,
  error,
  accept = '*',
  maxFiles = 10,
  maxSizeMB = 10,
  disabled = false,
}: FileUploadProps) {
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState<string>('');
  const errorId = `${id}-error`;
  const maxSizeBytes = maxSizeMB * 1024 * 1024;

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (!selectedFiles) return;
    setUploadError('');

    if (files.length + selectedFiles.length > maxFiles) {
      setUploadError(`Maximum ${maxFiles} files allowed`);
      return;
    }

    const newFiles: UploadedFile[] = [];
    for (const file of Array.from(selectedFiles)) {
      if (file.size > maxSizeBytes) {
        setUploadError(`File "${file.name}" exceeds ${maxSizeMB}MB limit`);
        return;
      }
      try {
        const uploaded = await fileToUploaded(file);
        newFiles.push(uploaded);
      } catch {
        setUploadError(`Failed to read file "${file.name}"`);
        return;
      }
    }

    newFiles.forEach((f) => onAddFile(f));
    if (inputRef.current) inputRef.current.value = '';
  };

  const handleRemove = (fileId: string) => {
    onRemoveFile(fileId);
    setUploadError('');
  };

  const displayError = uploadError || error;

  return (
    <div className="form-field" role="group">
      <label htmlFor={id} className="form-label">
        {label}
      </label>
      <div className="file-upload-area">
        <input
          ref={inputRef}
          id={id}
          type="file"
          onChange={handleChange}
          accept={accept}
          multiple
          disabled={disabled || files.length >= maxFiles}
          aria-describedby={displayError ? errorId : undefined}
          aria-invalid={!!displayError}
          style={{
            position: 'absolute',
            width: '1px',
            height: '1px',
            padding: '0',
            margin: '-1px',
            overflow: 'hidden',
            clip: 'rect(0, 0, 0, 0)',
            whiteSpace: 'nowrap',
            border: '0',
          }}
        />
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={disabled || files.length >= maxFiles}
          className="btn btn--secondary"
          aria-label={`Upload file for ${label}`}
        >
          Choose file{files.length > 0 ? 's' : ''}
        </button>
        <span className="file-upload-hint" aria-live="polite">
          {files.length > 0
            ? `${files.length} file${files.length > 1 ? 's' : ''} selected`
            : `Max ${maxFiles} files, ${maxSizeMB}MB each`}
        </span>
      </div>
      {files.length > 0 && (
        <ul className="file-list" aria-label="Uploaded files">
          {files.map((f) => (
            <li key={f.id} className="file-list-item">
              <span className="file-name">{f.name}</span>
              <span className="file-size">({(f.size / 1024).toFixed(1)} KB)</span>
              <button
                type="button"
                onClick={() => handleRemove(f.id)}
                className="btn btn--danger btn--small"
                aria-label={`Remove ${f.name}`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      {displayError && (
        <p id={errorId} className="form-error" role="alert">
          {displayError}
        </p>
      )}
    </div>
  );
}
