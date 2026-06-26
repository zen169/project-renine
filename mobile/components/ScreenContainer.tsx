import React from 'react';
import { StyleSheet, View, StatusBar, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { COLORS } from '../theme/colors';

interface ScreenContainerProps {
  children: React.ReactNode;
  scrollable?: boolean;
}

export const ScreenContainer = ({ children, scrollable = false }: ScreenContainerProps) => {
  const InnerView = scrollable ? ScrollView : View;

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor={COLORS.background} />
      
      {/* Subtle background glow effect */}
      <View style={styles.neonGlowTop} />
      <View style={styles.neonGlowBottom} />

      <InnerView 
        style={styles.container} 
        contentContainerStyle={scrollable ? styles.scrollContent : undefined}
        showsVerticalScrollIndicator={false}
      >
        {children}
      </InnerView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  container: {
    flex: 1,
    paddingHorizontal: 20,
    paddingTop: 10,
  },
  scrollContent: {
    paddingBottom: 40,
  },
  neonGlowTop: {
    position: 'absolute',
    top: -150,
    right: -150,
    width: 300,
    height: 300,
    borderRadius: 150,
    backgroundColor: COLORS.glow,
    opacity: 0.5,
  },
  neonGlowBottom: {
    position: 'absolute',
    bottom: -150,
    left: -150,
    width: 300,
    height: 300,
    borderRadius: 150,
    backgroundColor: 'rgba(189, 0, 255, 0.08)', // Violet subtle backing
    opacity: 0.4,
  },
});
