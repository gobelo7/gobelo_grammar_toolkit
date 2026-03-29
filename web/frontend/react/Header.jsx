
import logo from '../assets/gobelo_logo_warm.jpg';

export default function Header() {
  return (
    <header className="header">
      <img src={logo} alt="Gobelo Logo" className="logo" />
      <h1>Gobelo</h1>
    </header>
  );
}
