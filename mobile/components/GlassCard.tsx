import React from 'react';
import { StyleSheet, View, Text, ViewStyle } from 'react-native';
import { COLORS } from '../theme/colors';

interface GlassCardProps {
  children: React.ReactNode;
  title?: string;
  style?: ViewStyle;
  borderColor?: string;
}

export const GlassCard = ({ children, title, style, borderColor }: GlassCardProps) => {
  return (
    <View style={[styles.card, { borderColor: borderColor || COLORS.cardBorder }, style]}>
      {title && (
        <View style={styles.header}>
          <Text style={styles.title}>{title.toUpperCase()}</Text>
          <View style={styles.titleUnderline} />
        </View>
      )}
      <View style={styles.content}>
        {children}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: COLORS.cardBg,
    borderWidth: 1,
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    shadowColor: COLORS.primary,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 4,
  },
  header: {
    marginBottom: 12,
  },
  title: {
    color: COLORS.primary,
    fontFamily: 'System',
    fontWeight: 'bold',
    fontSize: 12,
    letterSpacing: 2,
  },
  titleUnderline: {
    height: 1,
    backgroundColor: COLORS.primary,
    width: 30,
    marginTop: 4,
    opacity: 0.8,
  },
  content: {
    width: '100%',
  },
});
