CREATE TABLE wallets(id integer PRIMARY KEY,balance integer NOT NULL CHECK(balance>=0));
