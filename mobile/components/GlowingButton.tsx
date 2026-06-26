import React from 'react';
import { StyleSheet, Text, TouchableOpacity, ActivityIndicator, ViewStyle, TextStyle } from 'react-native';
import { COLORS } from '../theme/colors';

interface GlowingButtonProps {
  onPress: () => void;
  title: string;
  variant?: 'primary' | 'secondary' | 'danger' | 'success';
  loading?: boolean;
  disabled?: boolean;
  style?: ViewStyle;
  textStyle?: TextStyle;
}

export const GlowingButton = ({
  onPress,
  title,
  variant = 'primary',
  loading = false,
  disabled = false,
  style,
  textStyle,
}: GlowingButtonProps) => {
  const getColors = () => {
    switch (variant) {
      case 'secondary':
        return { bg: COLORS.secondary, shadow: COLORS.secondary };
      case 'danger':
        return { bg: COLORS.danger, shadow: COLORS.danger };
      case 'success':
        return { bg: COLORS.success, shadow: COLORS.success };
      case 'primary':
      default:
        return { bg: COLORS.background, shadow: COLORS.primary };
    }
  };

  const colors = getColors();
  const isPrimaryOutline = variant === 'primary';

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled || loading}
      activeOpacity={0.8}
      style={[
        styles.button,
        isPrimaryOutline 
          ? { backgroundColor: 'transparent', borderColor: COLORS.primary, borderWidth: 1.5 }
          : { backgroundColor: colors.bg, borderColor: 'transparent' },
        {
          shadowColor: colors.shadow,
          opacity: disabled ? 0.5 : 1,
        },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={isPrimaryOutline ? COLORS.primary : COLORS.text} size="small" />
      ) : (
        <Text style={[
          styles.text, 
          isPrimaryOutline ? { color: COLORS.primary } : { color: COLORS.text },
          textStyle
        ]}>
          {title.toUpperCase()}
        </Text>
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    height: 48,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 16,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.6,
    shadowRadius: 10,
    elevation: 6,
    marginVertical: 8,
  },
  text: {
    fontFamily: 'System',
    fontWeight: 'bold',
    fontSize: 13,
    letterSpacing: 2,
  },
});
