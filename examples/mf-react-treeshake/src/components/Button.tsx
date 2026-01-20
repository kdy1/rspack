// Re-export Button from ui-lib with additional wrapper
import { Button as UIButton } from 'ui-lib';

interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary';
}

export const Button = ({ children, onClick, variant = 'primary' }: ButtonProps) => {
  return UIButton({ children, onClick, variant });
};

export default Button;
