import './App.css';
// Only import Button and Badge from ui-lib
// Other exports (Card, List, Modal, Tooltip, Avatar, Spinner) should be tree-shaken
import { Button, Badge } from 'ui-lib';

const App = () => {
  const handleClick = () => {
    console.log('Button clicked!');
  };

  return (
    <div className="content">
      <h1>MF React Tree-Shaking Example</h1>
      <p>
        This example demonstrates Module Federation with tree-shaking shared modules.
      </p>
      <p>
        Only <code>Button</code> and <code>Badge</code> are imported from <code>ui-lib</code>.
        Other exports should be tree-shaken from the final bundle.
      </p>

      <div className="demo-section">
        <h2>Components in use:</h2>
        <div className="demo-item">
          <Button onClick={handleClick}>Click Me</Button>
        </div>
        <div className="demo-item">
          <Badge color="#28a745">Active</Badge>
          <Badge color="#dc3545">Inactive</Badge>
        </div>
      </div>

      <div className="info-section">
        <h3>Tree-Shaking Info</h3>
        <p>
          When built for production, the following exports from <code>ui-lib</code>
          should NOT be in the bundle:
        </p>
        <ul>
          <li>Card</li>
          <li>List</li>
          <li>Modal</li>
          <li>Tooltip</li>
          <li>Avatar</li>
          <li>Spinner</li>
        </ul>
      </div>
    </div>
  );
};

export default App;
