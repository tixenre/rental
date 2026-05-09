import { createContext, useContext } from "react";

export type EquipmentDetailCtx = {
  openId: string | null;
  setOpenId: (id: string | null) => void;
};

const Ctx = createContext<EquipmentDetailCtx>({
  openId: null,
  setOpenId: () => {},
});

export const EquipmentDetailProvider = Ctx.Provider;
export const useEquipmentDetail = () => useContext(Ctx);
