import React, { ReactNode,  useState } from 'react';
import Grid from '@mui/material/Grid';
import Menu from './Menu';
import { getComponentByItem } from './components';

interface MyLayoutProps {
    sidebar?: ReactNode;
    content?: ReactNode;
}


const ContentDisplay: React.FC<MyLayoutProps> = () => {
    const [selectedMenuItem, setSelectedMenuItem] = useState<string>(null);

    const handleMenuItemClick = (item: string) => {
        setSelectedMenuItem(item);
    };

    const kontent = getComponentByItem(selectedMenuItem)

    return (
        <Grid container style={{ height: 'calc(100vh - 90px)', marginTop: 90 }}>
            {/* Left Sidebar (1/6) on desktop, full width on mobile */}
            <Grid item xs={12} sm={2} display="flex" alignItems="center">
                <Menu onItemClick={handleMenuItemClick} />
            </Grid>

            {/* Main Content (5/6) on desktop, full width on mobile */}
            <Grid item xs={12} sm={10} style={{ backgroundColor: 'lightgrey' }}>
                {kontent}
            </Grid>
        </Grid>
    );
};

export default ContentDisplay;