import React, { useState } from 'react';
import { StyleSheet, View, Text, TextInput, TextInputProps } from 'react-native';
import { COLORS } from '../theme/colors';

interface GlowingInputProps extends TextInputProps {
  label?: string;
}

export const GlowingInput = ({ label, ...props }: GlowingInputProps) => {
  const [isFocused, setIsFocused] = useState<boolean>(false);

  return (
    <View style={styles.container}>
      {label && <Text style={styles.label}>{label.toUpperCase()}</Text>}
      <TextInput
        style={[
          styles.input,
          isFocused ? styles.inputFocused : styles.inputUnfocused,
        ]}
        placeholderTextColor={COLORS.textMuted}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        {...props}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginVertical: 10,
    width: '100%',
  },
  label: {
    color: COLORS.textSecondary,
    fontSize: 10,
    fontWeight: 'bold',
    marginBottom: 6,
    letterSpacing: 1.5,
  },
  input: {
    height: 46,
    backgroundColor: '#0A0D23', // Extremely dark blue background for input box
    borderWidth: 1.5,
    borderRadius: 8,
    color: COLORS.text,
    paddingHorizontal: 14,
    fontSize: 14,
    fontFamily: 'System',
  },
  inputUnfocused: {
    borderColor: COLORS.cardBorder,
  },
  inputFocused: {
    borderColor: COLORS.primary,
    shadowColor: COLORS.primary,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5,
    shadowRadius: 6,
  },
});
