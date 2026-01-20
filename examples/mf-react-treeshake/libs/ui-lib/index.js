// UI Library with multiple exports for tree-shaking demo
// Only used exports should be included in the final bundle

export const Button = ({ children, onClick, variant = 'primary' }) => {
  const styles = {
    padding: '8px 16px',
    borderRadius: '4px',
    border: 'none',
    cursor: 'pointer',
    backgroundColor: variant === 'primary' ? '#007bff' : '#6c757d',
    color: 'white',
  };
  return React.createElement('button', { style: styles, onClick }, children);
};

export const Badge = ({ children, color = 'blue' }) => {
  const styles = {
    padding: '4px 8px',
    borderRadius: '12px',
    fontSize: '12px',
    backgroundColor: color,
    color: 'white',
  };
  return React.createElement('span', { style: styles }, children);
};

export const Card = ({ title, children }) => {
  const styles = {
    border: '1px solid #ddd',
    borderRadius: '8px',
    padding: '16px',
    marginBottom: '16px',
  };
  return React.createElement('div', { style: styles }, [
    React.createElement('h3', { key: 'title' }, title),
    React.createElement('div', { key: 'content' }, children),
  ]);
};

export const List = ({ items }) => {
  const styles = {
    listStyle: 'none',
    padding: 0,
  };
  return React.createElement(
    'ul',
    { style: styles },
    items.map((item, i) => React.createElement('li', { key: i }, item))
  );
};

export const Modal = ({ isOpen, onClose, title, children }) => {
  if (!isOpen) return null;
  const overlayStyles = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  };
  const modalStyles = {
    backgroundColor: 'white',
    padding: '24px',
    borderRadius: '8px',
    minWidth: '300px',
  };
  return React.createElement('div', { style: overlayStyles, onClick: onClose }, [
    React.createElement('div', { key: 'modal', style: modalStyles, onClick: e => e.stopPropagation() }, [
      React.createElement('h2', { key: 'title' }, title),
      React.createElement('div', { key: 'content' }, children),
    ]),
  ]);
};

export const Tooltip = ({ text, children }) => {
  const styles = {
    position: 'relative',
    display: 'inline-block',
  };
  return React.createElement('div', { style: styles, title: text }, children);
};

export const Avatar = ({ src, name, size = 40 }) => {
  const styles = {
    width: size,
    height: size,
    borderRadius: '50%',
    backgroundColor: '#ddd',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  };
  if (src) {
    return React.createElement('img', { src, alt: name, style: styles });
  }
  return React.createElement('div', { style: styles }, name?.[0] || '?');
};

export const Spinner = ({ size = 24 }) => {
  const styles = {
    width: size,
    height: size,
    border: '3px solid #f3f3f3',
    borderTop: '3px solid #007bff',
    borderRadius: '50%',
    animation: 'spin 1s linear infinite',
  };
  return React.createElement('div', { style: styles });
};

// Default export
export default {
  Button,
  Badge,
  Card,
  List,
  Modal,
  Tooltip,
  Avatar,
  Spinner,
};
