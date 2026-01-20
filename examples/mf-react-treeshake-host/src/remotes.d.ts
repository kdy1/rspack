declare module 'remote/App' {
  const App: React.ComponentType;
  export default App;
}

declare module 'remote/Button' {
  const Button: React.ComponentType<{
    children: React.ReactNode;
    onClick?: () => void;
    variant?: 'primary' | 'secondary';
  }>;
  export default Button;
}
