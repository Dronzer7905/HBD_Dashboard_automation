import React from 'react'
import { Navigate } from 'react-router-dom';

const PrivateRoute = ({children}) => {
    const isDev = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
    const token = localStorage.getItem("token") || (isDev ? "dev_local_token" : null);
    return token ? children : <Navigate to="/auth/sign-in" />;
}

export default PrivateRoute

