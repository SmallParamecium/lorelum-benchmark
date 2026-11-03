CREATE TABLE accounts(id serial PRIMARY KEY,account_key text NOT NULL,value integer NOT NULL CHECK(value>=0));
