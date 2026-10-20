import React, { useEffect, useCallback } from "react";

interface PermissionDialogProps {
  actionDescription: string;
  toolLabel?: string;
  onDeny: () => void;
  onAlwaysAllow: () => void;
  onAllowOnce: () => void;
}

const HandIcon: React.FC = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M10.25 2C11.0283 2 11.6867 2.50842 11.9141 3.21094C12.1623 3.07581 12.4475 3 12.75 3C13.7165 3 14.5 3.7835 14.5 4.75V6.16992C14.7275 6.06176 14.9814 6 15.25 6C16.2165 6 17 6.7835 17 7.75V11.25C17 14.9779 13.9779 18 10.25 18C6.52208 18 3.5 14.9779 3.5 11.25V8C3.5 7.44772 3.94772 7 4.5 7H5C5.36464 7 5.70563 7.09906 6 7.26953V4.75C6 3.7835 6.7835 3 7.75 3C8.05224 3 8.33688 3.07606 8.58496 3.21094C8.81229 2.50827 9.47163 2 10.25 2ZM10.25 3C9.83579 3 9.5 3.33579 9.5 3.75V9.5C9.5 9.77614 9.27614 10 9 10C8.72386 10 8.5 9.77614 8.5 9.5V4.75C8.5 4.33579 8.16421 4 7.75 4C7.33579 4 7 4.33579 7 4.75V11.002C8.32553 11.0277 9.48461 11.8814 9.90918 13.1221L9.98535 13.3789L10 13.4785C10.0102 13.711 9.85565 13.9267 9.62109 13.9854C9.38677 14.0438 9.1493 13.9264 9.04883 13.7168L9.01465 13.6211L8.96289 13.4463C8.66901 12.5877 7.85929 12 6.93848 12H6.5C6.22386 12 6 11.7761 6 11.5V9C6 8.44772 5.55228 8 5 8H4.5V11.25C4.5 14.4256 7.07436 17 10.25 17C13.4256 17 16 14.4256 16 11.25V7.75C16 7.33579 15.6642 7 15.25 7C14.8358 7 14.5 7.33579 14.5 7.75V10.5C14.5 10.7761 14.2761 11 14 11C13.7239 11 13.5 10.7761 13.5 10.5V4.75C13.5 4.33579 13.1642 4 12.75 4C12.3358 4 12 4.33579 12 4.75V9.5C12 9.77614 11.7761 10 11.5 10C11.2239 10 11 9.77614 11 9.5V3.75C11 3.33579 10.6642 3 10.25 3Z" />
  </svg>
);

export const PermissionDialog: React.FC<PermissionDialogProps> = ({
  actionDescription,
  toolLabel,
  onDeny,
  onAlwaysAllow,
  onAllowOnce,
}) => {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onDeny();
      } else if (e.key === "Enter" && e.ctrlKey) {
        e.preventDefault();
        onAlwaysAllow();
      } else if (e.key === "Enter" && !e.ctrlKey && !e.shiftKey && !e.altKey) {
        e.preventDefault();
        onAllowOnce();
      }
    },
    [onDeny, onAlwaysAllow, onAllowOnce]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return (
    <div role="dialog" className="permission-dialog" aria-labelledby="permission-dialog-title">
      {/* Header */}
      <div className="permission-dialog-header">
        <div className="permission-dialog-icon">
          <HandIcon />
        </div>
        <h3 id="permission-dialog-title">Permission required</h3>
      </div>

      {/* Description */}
      <div className="permission-dialog-description">
        Sentry wants to <span>{toolLabel || actionDescription}</span>
      </div>

      {/* Buttons */}
      <div className="permission-dialog-buttons">
        <button
          type="button"
          className="permission-dialog-btn"
          onClick={onDeny}
        >
          <span>Deny</span>
          <div className="permission-dialog-kbd-group">
            <kbd className="permission-kbd">Esc</kbd>
          </div>
        </button>

        <button
          type="button"
          className="permission-dialog-btn"
          onClick={onAlwaysAllow}
        >
          <span style={{ textAlign: "left" }}>Always allow</span>
          <div className="permission-dialog-kbd-group">
            <kbd className="permission-kbd">Ctrl</kbd>
            <kbd className="permission-kbd">Enter</kbd>
          </div>
        </button>

        <button
          type="button"
          className="permission-dialog-btn permission-dialog-btn-highlight"
          onClick={onAllowOnce}
        >
          <span>Allow once</span>
          <div className="permission-dialog-kbd-group">
            <kbd className="permission-kbd">Enter</kbd>
          </div>
        </button>
      </div>
    </div>
  );
};

export default PermissionDialog;
