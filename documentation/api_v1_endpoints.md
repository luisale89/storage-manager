# API v1 endpoints

`** http errors and JSON responses**`
* *url not found* -> `http code: 404`
```json
    {
        "data": {},
        "message": "<error message info>",
        "result": "error"
    }
```

* *internal server error* -> `http code: 500`
```json
    {
        "data": {},
        "message": "<error message info>",
        "result": "error"
    }
```

---
`** auth endpoints **`
---


## `POST` **sign-up**

    endpoint para crear un nuevo usuario en la base de datos

* *url*
    ```http
    POST /api/v1/auth/sign-up
    ```

    | Parameter | Type | Description | Required
    | :--- | :--- | :--- | :---
    | | | | 
***

* *headers*
    ```json
    {
        "content-type":"application/json"
    }
    ```

* *JSON body*
    ```json
    {
        "email": "<user_email>",
        "password": "<user_password>",
        "fname": "<user_first_name>",
        "lname": "<user_last_name>"
    }
    ```

    | Parameter | Type | Description | Required
    | :--- | :--- | :--- | :---
    | "email" | `string` | user email | `True` 
    | "password" | `string` | user password | `True`
    | "fname" | `string` | user first name (only letters) | `True`
    | "lname" | `string` | user last name (only letters) | `True`


* *JSON responses*
    - *email alredy exists* -> `http code: 409`
    ```json
    {
        "data": {},
        "message": "<error message info>",
        "result": "error"
    }
    ```
    - *bad input format* -> `http code: 400`
    ```json
    {
        "data": {
            "invalid": {
                "<parameter1>": "<invalid parameter message>",
                "<parameter2>": "<invalid parameter message>"
            }
        },
        "message": "<error message info>",
        "result": "error"
    }
    ```
    - *new user created* -> `http code: 201`
    ```json 
    {
        "data": {},
        "message": "<success message>",
        "result": "success"
    }
    ```