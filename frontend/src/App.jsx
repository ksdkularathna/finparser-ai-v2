import { useState, useRef, useCallback } from 'react';
import './App.css';

function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState({ type: '', message: '' });
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);

    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.type === 'application/pdf') {
      setFile(droppedFile);
      setStatus({ type: '', message: '' });
    } else {
      setStatus({ type: 'error', message: 'Please upload a PDF file' });
    }
  }, []);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setStatus({ type: '', message: '' });
    }
  };

  const handleRemoveFile = () => {
    setFile(null);
    setStatus({ type: '', message: '' });
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleConvert = async () => {
    if (!file) return;

    setLoading(true);
    setStatus({ type: '', message: '' });

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/convert', {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `bank_statement_${file.name.replace('.pdf', '')}.xlsx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        setStatus({
          type: 'success',
          message: 'Conversion successful! Your Excel file has been downloaded.'
        });
        setFile(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Conversion failed');
      }
    } catch (error) {
      console.error('Conversion failed:', error);
      setStatus({
        type: 'error',
        message: error.message || 'Failed to convert file. Please try again.'
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <header className="header">
        <div className="logo">
          <div className="logo-icon">📊</div>
          <h1 className="title">Bank Statement Extractor</h1>
        </div>
        <p className="subtitle">
          Transform your bank statement PDFs into organized Excel spreadsheets
        </p>
      </header>

      <main className="upload-card">
        <div
          className={`dropzone ${dragOver ? 'drag-over' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <div className="dropzone-content">
            <span className="dropzone-icon">📄</span>
            <p className="dropzone-text">
              <strong>Click to upload</strong> or drag and drop
            </p>
            <p className="dropzone-hint">PDF files only (max 50MB)</p>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handleFileChange}
            className="file-input"
          />
        </div>

        {file && (
          <div className="file-info">
            <div className="file-icon">📑</div>
            <div className="file-details">
              <div className="file-name">{file.name}</div>
              <div className="file-size">{formatFileSize(file.size)}</div>
            </div>
            <button
              className="remove-file"
              onClick={handleRemoveFile}
              aria-label="Remove file"
            >
              ✕
            </button>
          </div>
        )}

        <button
          className="convert-btn"
          onClick={handleConvert}
          disabled={!file || loading}
        >
          {loading ? (
            <>
              <div className="loading-spinner"></div>
              Converting...
            </>
          ) : (
            <>
              <span>⚡</span>
              Convert to Excel
            </>
          )}
        </button>

        {status.message && (
          <div className={`status-message ${status.type}`}>
            <span className="status-icon">
              {status.type === 'success' ? '✓' : '⚠'}
            </span>
            <span>{status.message}</span>
          </div>
        )}
      </main>

      <div className="features">
        <div className="feature">
          <span className="feature-icon">🔒</span>
          <span>Secure Processing</span>
        </div>
        <div className="feature">
          <span className="feature-icon">⚡</span>
          <span>Instant Conversion</span>
        </div>
        <div className="feature">
          <span className="feature-icon">📊</span>
          <span>Formatted Output</span>
        </div>
      </div>

      <footer className="footer">
        Built with ❤️ for seamless document processing
      </footer>
    </div>
  );
}

export default App;
