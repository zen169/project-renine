import React, { ComponentProps } from 'react';
import { View, TouchableOpacity, StyleSheet, Text, ActivityIndicator } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';

import { useAuth } from '../services/auth';
import { COLORS } from '../theme/colors';

import { LoginScreen } from '../screens/LoginScreen';
import { MemoryScreen } from '../screens/MemoryScreen';
import { SmartHomeScreen } from '../screens/SmartHomeScreen';
import { PetsScreen } from '../screens/PetsScreen';
import { RemindersScreen } from '../screens/RemindersScreen';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

// Custom Header Logout Button
const HeaderLogoutButton = () => {
  const { logout } = useAuth();
  return (
    <TouchableOpacity onPress={logout} style={styles.logoutButton} activeOpacity={0.7}>
      <Ionicons name="log-out-outline" size={20} color={COLORS.danger} />
      <Text style={styles.logoutText}>DISCONNECT</Text>
    </TouchableOpacity>
  );
};

// Main App Dashboard Bottom Tab Navigation
const TabNavigator = () => {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ color, size }) => {
          let iconName: ComponentProps<typeof Ionicons>['name'] = 'ellipse';

          if (route.name === 'Memory') {
            iconName = 'bulb-outline';
          } else if (route.name === 'Smart Home') {
            iconName = 'home-outline';
          } else if (route.name === 'Pets') {
            iconName = 'paw-outline';
          } else if (route.name === 'Reminders') {
            iconName = 'alarm-outline';
          }

          return <Ionicons name={iconName} size={size} color={color} />;
        },
        tabBarActiveTintColor: COLORS.primary,
        tabBarInactiveTintColor: COLORS.textSecondary,
        tabBarStyle: {
          backgroundColor: COLORS.background,
          borderTopWidth: 1.5,
          borderTopColor: COLORS.cardBorder,
          height: 60,
          paddingBottom: 8,
          paddingTop: 8,
        },
        tabBarLabelStyle: {
          fontSize: 9,
          fontWeight: 'bold',
          letterSpacing: 1,
        },
        headerStyle: {
          backgroundColor: COLORS.background,
          borderBottomWidth: 1.5,
          borderBottomColor: COLORS.cardBorder,
          shadowOpacity: 0,
          elevation: 0,
        },
        headerTitleStyle: {
          color: COLORS.primary,
          fontSize: 14,
          fontWeight: '900',
          letterSpacing: 2,
        },
        headerRight: () => <HeaderLogoutButton />,
      })}
    >
      <Tab.Screen name="Memory" component={MemoryScreen} options={{ title: 'MEMORY MATRIX' }} />
      <Tab.Screen name="Smart Home" component={SmartHomeScreen} options={{ title: 'SMART INTERFACE' }} />
      <Tab.Screen name="Pets" component={PetsScreen} options={{ title: 'BIO TRACKING' }} />
      <Tab.Screen name="Reminders" component={RemindersScreen} options={{ title: 'CRON CORE' }} />
    </Tab.Navigator>
  );
};

// Root Navigator
export const AppNavigator = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={styles.loadingText}>SYNCHRONIZING SECURE TUNNEL...</Text>
      </View>
    );
  }

  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {!isAuthenticated ? (
          <Stack.Screen name="Login" component={LoginScreen} />
        ) : (
          <Stack.Screen name="Home" component={TabNavigator} />
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
};



const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    backgroundColor: COLORS.background,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: COLORS.primary,
    fontSize: 10,
    fontWeight: 'bold',
    marginTop: 16,
    letterSpacing: 2,
  },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: 16,
    borderWidth: 1,
    borderColor: COLORS.danger,
    borderRadius: 6,
    paddingVertical: 4,
    paddingHorizontal: 8,
    backgroundColor: 'rgba(255, 0, 85, 0.03)',
  },
  logoutText: {
    color: COLORS.danger,
    fontSize: 8,
    fontWeight: 'bold',
    marginLeft: 4,
    letterSpacing: 1.5,
  },
});
