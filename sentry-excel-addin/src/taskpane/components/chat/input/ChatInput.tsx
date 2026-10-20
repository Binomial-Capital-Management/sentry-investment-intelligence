/**
 * ChatInput - TipTap/ProseMirror based input component
 * Replaces native textarea for better cursor/focus handling (matches Claude's implementation)
 */

import React, { useEffect, useImperativeHandle, forwardRef, useCallback } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import { Extension } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  placeholder?: string;
  disabled?: boolean;
}

export interface ChatInputHandle {
  focus: () => void;
  blur: () => void;
  clear: () => void;
  setValue: (text: string) => void;
}

export const ChatInput = forwardRef<ChatInputHandle, ChatInputProps>(
  ({ value, onChange, onSubmit, placeholder = "Reply", disabled = false }, ref) => {
    // Store onSubmit in a ref to avoid recreating the extension
    const onSubmitRef = React.useRef(onSubmit);
    onSubmitRef.current = onSubmit;

    // Create a custom extension for Enter key handling
    const EnterHandler = useCallback(() => {
      return Extension.create({
        name: "enterHandler",
        addKeyboardShortcuts() {
          return {
            "Shift-Enter": () => false, // Allow newline
            Enter: ({ editor }) => {
              const text = editor.getText().trim();
              if (text) {
                onSubmitRef.current();
                editor.commands.clearContent();
              }
              return true; // Prevent default (newline)
            },
          };
        },
      });
    }, []);

    const editor = useEditor({
      extensions: [
        StarterKit.configure({
          heading: false,
          bulletList: false,
          orderedList: false,
          blockquote: false,
          codeBlock: false,
          horizontalRule: false,
        }),
        Placeholder.configure({
          placeholder,
        }),
        EnterHandler(),
      ],
      content: "",
      editable: !disabled,
      onUpdate: ({ editor }) => {
        onChange(editor.getText());
      },
    });

    // Expose focus/blur/clear methods via ref
    useImperativeHandle(ref, () => ({
      focus: () => editor?.commands.focus(),
      blur: () => editor?.commands.blur(),
      clear: () => editor?.commands.clearContent(),
      setValue: (text: string) => {
        editor?.commands.setContent(text);
        editor?.commands.focus("end");
      },
    }));

    // Sync disabled state
    useEffect(() => {
      if (editor) {
        editor.setEditable(!disabled);
      }
    }, [editor, disabled]);

    // Sync editor content with value prop (clear when value becomes empty)
    useEffect(() => {
      if (editor && value === "" && editor.getText().trim() !== "") {
        editor.commands.clearContent();
      }
    }, [editor, value]);

    // Auto-focus when enabled
    useEffect(() => {
      if (editor && !disabled) {
        editor.commands.focus();
      }
    }, [editor, disabled]);

    return (
      <div 
        className="chat-input-wrapper"
        style={{ opacity: disabled ? 0.5 : 1 }}
      >
        <EditorContent editor={editor} className="tiptap" />
      </div>
    );
  }
);

ChatInput.displayName = "ChatInput";
