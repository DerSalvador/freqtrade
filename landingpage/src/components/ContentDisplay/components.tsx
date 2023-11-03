import React, { ReactNode } from 'react';
import Scroller from '../SupportedExchanges';
import Kubernetes from '../Kubernetes';
import ContactForm from '../ContactForm/ContactForm';
import Onboarding from '../WhatWeOffer';
import About from '../About';

// Define the type for your components array
type ComponentItem = {
    item: string;
    component: ReactNode;
};

// Array of components
export const components: ComponentItem[] = [
    {
        item: 'What we offer',
        component: <Onboarding />
    },   
    {
        item: 'Why Kubernetes',
        component: <Kubernetes />,
    },
    {
        item: 'Contact via Telegram',
        component: <ContactForm />
    },
    {
        item: 'About',
        component: <About />
    }
];

// Function to get the component based on the item
export const getComponentByItem = (item: string): ReactNode | null => {
    const componentItem = components.find((comp) => comp.item === item);
    return componentItem ? componentItem.component : null;
};

export const extractAllItems = (components: ComponentItem[]): string[] => {
    return components.map((component) => component.item);
};