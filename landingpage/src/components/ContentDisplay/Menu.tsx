import React, { useState } from 'react';
import { components, extractAllItems } from './components';
import "./Menu.css"; 
import { CSSProperties } from '@mui/material/styles/createMixins';

interface MenuProps {
    onItemClick: (item: string) => void;
}

const defaultStyles:CSSProperties = {
    fontSize: '24px',
    paddingTop: '30px',
    paddingBottom: '30px',
    cursor: 'pointer',
    padding: '8px 16px',
    backgroundColor: 'transparent',
    margin: 0,
    paddingLeft: '20px',
    display:'flex',
    justifyContent:'center',
};
const allItems = extractAllItems(components);

const Menu: React.FC<MenuProps> = ({ onItemClick }) => {
    const [activeItem, setActiveItem] = useState<string>(allItems[0]);

    const onClick = (item: string) => {
        onItemClick(item);
        setActiveItem(item);
    };

    return (
        <ul style={{ width: '100%', listStyleType: 'none', margin: 0, padding: 0 ,}}>
            {allItems.map((item, index) => (
                <li
                    key={index}
                    onClick={() => onClick(item)} // Pass the item to onClick
                    style={{...defaultStyles,
                        backgroundColor: activeItem === item ? 'lightgrey' : 'transparent'}}
                >
                    {item}
                </li>
            ))}
        </ul>
    );
};

export default Menu;





