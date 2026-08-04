import { useForm } from '../../context/FormContext';
import { FileUpload } from '../shared/FileUpload';
import type { UploadedFile } from '../../types';

export function DocumentUploadStep() {
  const { state, dispatch } = useForm();

  const handleAddFile = (file: UploadedFile) => {
    dispatch({ type: 'ADD_FILE', file });
  };

  const handleRemoveFile = (fileId: string) => {
    dispatch({ type: 'REMOVE_FILE', fileId });
  };

  return (
    <fieldset className="step-content">
      <legend className="step-legend">
        <h2>Supporting Documents</h2>
      </legend>
      <p className="step-description">
        Upload any documents that support your claim. Accepted formats: PDF, JPG, PNG, DOC.
        Please include photos of damage, receipts, police reports, and any other relevant documents.
      </p>

      <FileUpload
        label="Upload Documents"
        files={state.data.documents}
        onAddFile={handleAddFile}
        onRemoveFile={handleRemoveFile}
        accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
        maxFiles={10}
        maxSizeMB={10}
      />

      <div className="hint-box" aria-live="polite">
        <p>
          <strong>Tip:</strong> Clear, well-lit photos of the damage help speed up your claim processing.
          You can upload up to 10 files (max 10MB each).
        </p>
      </div>
    </fieldset>
  );
}
