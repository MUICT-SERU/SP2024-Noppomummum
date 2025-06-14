// app/project/[id]/components/SecondaryMenu/index.tsx
import { useState, useCallback, useEffect } from 'react';
import TabMenu from './components/TabMenu';
import TestSetup from '@/app/project/[id]/components/SecondaryMenu/components/TestSetup';
import TestCase from '@/app/project/[id]/components/SecondaryMenu/components/TestCase';
import { Block } from '@/app/types';
import styles from './SecondaryMenu.module.css';

interface SecondaryMenuProps {
    activeTab: string | null;
    blocks: Block[];
    onBlocksUpdate: (blocks: Block[], totalBlocks: number) => void;
    isDraggingBlock: boolean;
    projectType: string;
}

const SecondaryMenu = ({
    activeTab: initialActiveTab,
    isDraggingBlock,
    projectType
}: SecondaryMenuProps) => {
    const [activeTab, setActiveTab] = useState<string | null>(initialActiveTab);
    const [openMenuItem, setOpenMenuItem] = useState<string | null>(null);

    // Force window resize event when the component mounts
    useEffect(() => {
        // Give time for the component to fully render
        const timer = setTimeout(() => {
            window.dispatchEvent(new Event('resize'));
        }, 100);

        return () => clearTimeout(timer);
    }, []);

    const handleMenuItemClick = useCallback((item: string) => {
        setOpenMenuItem(openMenuItem === item ? null : item);
    }, [openMenuItem]);

    const handleTabClick = useCallback((tab: string) => {
        setActiveTab(activeTab === tab ? null : tab);
    }, [activeTab]);

    return (
        <div className={styles.secondarySidebar}>
            <TabMenu
                activeTab={activeTab}
                onTabClick={handleTabClick}
                tabs={[
                    { id: 'Setup', label: 'Test Setup' },
                    { id: 'Test case', label: 'Prompt Test Case' }
                ]}
            />
            <div className={styles.menuList}>
                {activeTab === 'Setup' ? (
                    <TestSetup
                        openMenuItem={openMenuItem}
                        handleMenuItemClick={handleMenuItemClick}
                        isDraggingBlock={isDraggingBlock}
                        projectType={projectType}
                    />
                ) : activeTab === 'Test case' ? (
                    <TestCase
                        openMenuItem={openMenuItem}
                        handleMenuItemClick={handleMenuItemClick}
                        isDraggingBlock={isDraggingBlock}
                    />
                ) : null}
            </div>
        </div>
    );
};

export default SecondaryMenu;