"""Message list editor for QueueSend.

Provides a list-based message editor where each item can contain
multi-line text. Enter key inserts newlines (not submit).

See Executable Spec Section 5 for requirements.
"""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class MessageTextEdit(QTextEdit):
    """Multi-line text editor that captures Enter for newlines.

    Enter inserts newline instead of submitting (Spec 5.1).
    """

    # Emitted when focus is lost or editing is done
    editing_finished = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setPlaceholderText("输入消息内容...")
        # Auto-adjust height
        self.setMinimumHeight(60)
        self.setMaximumHeight(150)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events.

        Enter/Return inserts newline (Spec 5.1).
        Escape finishes editing.
        """
        if event.key() == Qt.Key.Key_Escape:
            self.editing_finished.emit()
            self.clearFocus()
        else:
            # Enter key naturally inserts newline in QTextEdit
            super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:
        """Handle focus out to signal editing finished."""
        super().focusOutEvent(event)
        self.editing_finished.emit()


class MessageListItem(QWidget):
    """A single message item in the list.

    Contains a multi-line text editor and delete button.
    """

    content_changed = Signal()
    delete_requested = Signal()

    def __init__(self, content: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Text editor
        self._editor = MessageTextEdit()
        self._editor.setPlainText(content)
        self._editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._editor, 1)

        # Delete button
        self._delete_btn = QPushButton("×")
        self._delete_btn.setFixedSize(24, 24)
        self._delete_btn.setToolTip("删除此消息")
        self._delete_btn.clicked.connect(self.delete_requested.emit)
        layout.addWidget(self._delete_btn, 0, Qt.AlignmentFlag.AlignTop)

    def _on_text_changed(self) -> None:
        """Handle text changes."""
        self.content_changed.emit()

    def get_content(self) -> str:
        """Get the message content."""
        return self._editor.toPlainText()

    def set_content(self, content: str) -> None:
        """Set the message content."""
        self._editor.setPlainText(content)

    def is_empty(self) -> bool:
        """Check if content is empty or whitespace only."""
        return self.get_content().strip() == ""

    def set_editable(self, editable: bool) -> None:
        """Enable or disable editing."""
        self._editor.setReadOnly(not editable)
        self._delete_btn.setEnabled(editable)


class MessageEditor(QWidget):
    """Message list editor with auto-append empty item behavior.

    Features (per Spec 5.1):
    - One message per list item, items support multi-line
    - Enter inserts newline (not submit)
    - Auto-append empty item when last becomes non-empty
    - Start filters empty items and locks N
    """

    messages_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()

        self._add_btn = QPushButton("+ 添加消息")
        self._add_btn.clicked.connect(self._add_empty_item)
        toolbar.addWidget(self._add_btn)

        self._clear_btn = QPushButton("清空全部")
        self._clear_btn.clicked.connect(self._clear_all)
        toolbar.addWidget(self._clear_btn)

        toolbar.addStretch()

        self._count_label = QPushButton("0 条消息")
        self._count_label.setFlat(True)
        self._count_label.setEnabled(False)
        toolbar.addWidget(self._count_label)

        layout.addLayout(toolbar)

        # Message list
        self._list = QListWidget()
        self._list.setSpacing(4)
        layout.addWidget(self._list)

        # Initialize with one empty item
        self._add_empty_item()

    def _add_empty_item(self) -> None:
        """Add an empty message item at the end."""
        self._add_item("")

    def _add_item(self, content: str) -> MessageListItem:
        """Add a message item with given content.

        Args:
            content: Initial message content

        Returns:
            The created MessageListItem
        """
        item_widget = MessageListItem(content)
        item_widget.content_changed.connect(self._on_item_changed)
        item_widget.delete_requested.connect(
            lambda: self._delete_item(item_widget)
        )

        list_item = QListWidgetItem()
        list_item.setSizeHint(item_widget.sizeHint())
        self._list.addItem(list_item)
        self._list.setItemWidget(list_item, item_widget)

        self._update_count()
        return item_widget

    def _delete_item(self, item_widget: MessageListItem) -> None:
        """Delete a message item."""
        for i in range(self._list.count()):
            list_item = self._list.item(i)
            if self._list.itemWidget(list_item) == item_widget:
                self._list.takeItem(i)
                break

        # Ensure at least one empty item exists
        if self._list.count() == 0:
            self._add_empty_item()

        self._update_count()
        self.messages_changed.emit()

    def _clear_all(self) -> None:
        """Clear all messages."""
        self._list.clear()
        self._add_empty_item()
        self.messages_changed.emit()

    def _on_item_changed(self) -> None:
        """Handle content change in any item.

        Auto-append empty item when last becomes non-empty (Spec 5.1).
        """
        # Check if last item is non-empty
        if self._list.count() > 0:
            last_item = self._list.item(self._list.count() - 1)
            last_widget = self._list.itemWidget(last_item)
            if last_widget and not last_widget.is_empty():
                self._add_empty_item()

        self._update_count()
        self.messages_changed.emit()

    def _update_count(self) -> None:
        """Update the message count display."""
        valid_count = len(self.get_messages())
        self._count_label.setText(f"{valid_count} 条消息")

    def get_raw_messages(self) -> list[str]:
        """Get all messages including empty ones."""
        messages = []
        for i in range(self._list.count()):
            list_item = self._list.item(i)
            widget = self._list.itemWidget(list_item)
            if widget:
                messages.append(widget.get_content())
        return messages

    def get_messages(self) -> list[str]:
        """Get filtered messages (non-empty only).

        Implements the filter logic from Spec 5.1:
        messages = [m for m in messages_raw if trim(m) != ""]
        """
        return [m.strip() for m in self.get_raw_messages() if m.strip()]

    def set_messages(self, messages: list[str]) -> None:
        """Set messages from a list.

        Args:
            messages: List of message strings
        """
        self._list.clear()
        for msg in messages:
            self._add_item(msg)
        # Ensure empty item at end
        if self._list.count() == 0 or not self._get_last_widget().is_empty():
            self._add_empty_item()
        self._update_count()

    def _get_last_widget(self) -> Optional[MessageListItem]:
        """Get the last item's widget."""
        if self._list.count() == 0:
            return None
        last_item = self._list.item(self._list.count() - 1)
        return self._list.itemWidget(last_item)

    def set_editable(self, editable: bool) -> None:
        """Enable or disable editing of all items.

        Args:
            editable: Whether messages can be edited
        """
        for i in range(self._list.count()):
            list_item = self._list.item(i)
            widget = self._list.itemWidget(list_item)
            if widget:
                widget.set_editable(editable)

        self._add_btn.setEnabled(editable)
        self._clear_btn.setEnabled(editable)

    def get_snapshot(self) -> list[str]:
        """Get a snapshot of current messages for change detection.

        Used for Pause/Resume message change detection (Spec 10.1).
        """
        return self.get_messages().copy()

    def has_changed(self, snapshot: list[str]) -> bool:
        """Check if messages have changed since snapshot.

        Args:
            snapshot: Previous snapshot from get_snapshot()

        Returns:
            True if messages have changed
        """
        return self.get_messages() != snapshot


